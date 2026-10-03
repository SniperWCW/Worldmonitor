"""Geo helpers for Lage Monitor (pure Python, no Home Assistant imports).

Provides:
* a gazetteer of German cities, states and neighbouring countries,
* word-boundary place matching (no more "Interessen" -> Essen),
* Bundesland detection from Presseportal prefixes such as ``POL-HH:``,
* the "(ots)" dateline of police press releases as a precise location hint,
* a coarse Germany outline (the old bounding box also covered Basel,
  Salzburg, Prague, Szczecin ...) and a "neighbourhood" check for the area
  around Germany.

All coordinates are approximate (about 0.01 degree). Border checks are only
accurate to roughly 10-20 km, which is fine for scoring and map markers.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
import unicodedata

# ---------------------------------------------------------------------------
# Text folding
# ---------------------------------------------------------------------------

_UMLAUT_FOLD = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                              "Ä": "ae", "Ö": "oe", "Ü": "ue"})


def _strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def fold(text: str) -> str:
    """Lowercase, ä->ae, ö->oe, ü->ue, ß->ss, other diacritics stripped."""
    return _strip_diacritics(str(text or "").translate(_UMLAUT_FOLD).lower())


def fold_plain(text: str) -> str:
    """Lowercase with diacritics simply removed (ü->u), as many feeds do."""
    lowered = str(text or "").lower().replace("ß", "ss")
    return _strip_diacritics(lowered)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

# code: (name, centroid lat, centroid lon)
STATES: dict[str, tuple[str, float, float]] = {
    "BW": ("Baden-Württemberg", 48.66, 9.35),
    "BY": ("Bayern", 48.95, 11.40),
    "BE": ("Berlin", 52.52, 13.40),
    "BB": ("Brandenburg", 52.45, 13.00),
    "HB": ("Bremen", 53.08, 8.80),
    "HH": ("Hamburg", 53.55, 9.99),
    "HE": ("Hessen", 50.65, 9.00),
    "MV": ("Mecklenburg-Vorpommern", 53.75, 12.60),
    "NI": ("Niedersachsen", 52.80, 9.40),
    "NW": ("Nordrhein-Westfalen", 51.45, 7.55),
    "RP": ("Rheinland-Pfalz", 49.95, 7.45),
    "SL": ("Saarland", 49.38, 6.98),
    "SN": ("Sachsen", 51.05, 13.35),
    "ST": ("Sachsen-Anhalt", 51.95, 11.70),
    "SH": ("Schleswig-Holstein", 54.20, 9.70),
    "TH": ("Thüringen", 50.90, 11.00),
}

STATE_ALIASES: dict[str, tuple[str, ...]] = {
    "BW": ("baden-württemberg", "baden-wuerttemberg"),
    "BY": ("bayern", "freistaat bayern"),
    "BE": (),  # city state: handled as city "Berlin"
    "BB": ("brandenburg",),
    "HB": (),
    "HH": (),
    "HE": ("hessen",),
    "MV": ("mecklenburg-vorpommern", "mecklenburg"),
    "NI": ("niedersachsen",),
    "NW": ("nordrhein-westfalen", "nrw"),
    "RP": ("rheinland-pfalz",),
    "SL": ("saarland",),
    "SN": ("sachsen",),
    "ST": ("sachsen-anhalt",),
    "SH": ("schleswig-holstein",),
    "TH": ("thüringen", "thueringen"),
}

# country code: (name, centroid lat, centroid lon)
COUNTRIES: dict[str, tuple[str, float, float]] = {
    "DE": ("Deutschland", 51.16, 10.45),
    "PL": ("Polen", 52.00, 19.40),
    "CZ": ("Tschechien", 49.80, 15.50),
    "AT": ("Österreich", 47.60, 14.10),
    "CH": ("Schweiz", 46.80, 8.20),
    "FR": ("Frankreich", 46.60, 2.40),
    "NL": ("Niederlande", 52.20, 5.30),
    "BE": ("Belgien", 50.60, 4.70),
    "LU": ("Luxemburg", 49.80, 6.10),
    "DK": ("Dänemark", 56.00, 9.50),
    "LT": ("Litauen", 55.30, 23.90),
    "LV": ("Lettland", 56.90, 24.90),
    "EE": ("Estland", 58.70, 25.50),
    "UA": ("Ukraine", 49.00, 31.40),
    "RU": ("Russland", 60.00, 60.00),
}

COUNTRY_ALIASES: dict[str, tuple[str, ...]] = {
    "PL": ("polen", "polnisch"),
    "CZ": ("tschechien", "tschechische republik"),
    "AT": ("österreich", "oesterreich"),
    "CH": ("schweiz",),
    "FR": ("frankreich",),
    "NL": ("niederlande", "holland"),
    "BE": ("belgien",),
    "LU": ("luxemburg",),
    "DK": ("dänemark", "daenemark"),
    "LT": ("litauen",),
    "LV": ("lettland",),
    "EE": ("estland",),
    "UA": ("ukraine",),
    "RU": ("russland",),
    "DE": ("deutschland",),
}

# Countries around Germany ("Umgebung"). Ukraine/Russia are "world" here,
# except Kaliningrad which borders Poland and Lithuania.
NEIGHBOR_COUNTRIES: frozenset[str] = frozenset(
    {"PL", "CZ", "AT", "CH", "FR", "NL", "BE", "LU", "DK", "LT", "LV", "EE"}
)

# name: (lat, lon, country, state or None, ambiguous?)
# German entries carry the state; "ambiguous" names need a preceding
# preposition ("in Essen") because they are also common nouns or names.
_CITY_ROWS: tuple[tuple[str, float, float, str, str | None, bool], ...] = (
    # -- Germany -----------------------------------------------------------
    ("Berlin", 52.520, 13.405, "DE", "BE", False),
    ("Hamburg", 53.551, 9.994, "DE", "HH", False),
    ("München", 48.135, 11.582, "DE", "BY", False),
    ("Köln", 50.938, 6.960, "DE", "NW", False),
    ("Frankfurt am Main", 50.110, 8.682, "DE", "HE", False),
    ("Frankfurt", 50.110, 8.682, "DE", "HE", False),
    ("Frankfurt (Oder)", 52.347, 14.551, "DE", "BB", False),
    ("Stuttgart", 48.776, 9.183, "DE", "BW", False),
    ("Düsseldorf", 51.228, 6.774, "DE", "NW", False),
    ("Leipzig", 51.340, 12.373, "DE", "SN", False),
    ("Dortmund", 51.514, 7.465, "DE", "NW", False),
    ("Essen", 51.456, 7.012, "DE", "NW", True),
    ("Bremen", 53.079, 8.802, "DE", "HB", False),
    ("Dresden", 51.050, 13.738, "DE", "SN", False),
    ("Hannover", 52.376, 9.732, "DE", "NI", False),
    ("Nürnberg", 49.452, 11.077, "DE", "BY", False),
    ("Duisburg", 51.434, 6.762, "DE", "NW", False),
    ("Bochum", 51.482, 7.216, "DE", "NW", False),
    ("Wuppertal", 51.256, 7.150, "DE", "NW", False),
    ("Bielefeld", 52.030, 8.533, "DE", "NW", False),
    ("Bonn", 50.737, 7.098, "DE", "NW", False),
    ("Münster", 51.961, 7.626, "DE", "NW", False),
    ("Karlsruhe", 49.007, 8.404, "DE", "BW", False),
    ("Mannheim", 49.488, 8.466, "DE", "BW", False),
    ("Augsburg", 48.371, 10.898, "DE", "BY", False),
    ("Wiesbaden", 50.078, 8.240, "DE", "HE", False),
    ("Gelsenkirchen", 51.518, 7.086, "DE", "NW", False),
    ("Mönchengladbach", 51.195, 6.442, "DE", "NW", False),
    ("Braunschweig", 52.269, 10.521, "DE", "NI", False),
    ("Chemnitz", 50.828, 12.921, "DE", "SN", False),
    ("Kiel", 54.323, 10.123, "DE", "SH", False),
    ("Aachen", 50.775, 6.084, "DE", "NW", False),
    ("Halle (Saale)", 51.482, 11.970, "DE", "ST", False),
    ("Halle", 51.482, 11.970, "DE", "ST", True),
    ("Magdeburg", 52.121, 11.628, "DE", "ST", False),
    ("Dessau-Roßlau", 51.836, 12.230, "DE", "ST", False),
    ("Bremerhaven", 53.540, 8.581, "DE", "HB", False),
    ("Erfurt", 50.985, 11.030, "DE", "TH", False),
    ("Jena", 50.927, 11.589, "DE", "TH", False),
    ("Gera", 50.877, 12.082, "DE", "TH", False),
    ("Weimar", 50.980, 11.329, "DE", "TH", False),
    ("Mainz", 49.993, 8.247, "DE", "RP", False),
    ("Ludwigshafen", 49.477, 8.445, "DE", "RP", False),
    ("Koblenz", 50.357, 7.589, "DE", "RP", False),
    ("Trier", 49.756, 6.642, "DE", "RP", False),
    ("Kaiserslautern", 49.444, 7.769, "DE", "RP", False),
    ("Worms", 49.633, 8.351, "DE", "RP", False),
    ("Speyer", 49.318, 8.431, "DE", "RP", False),
    ("Saarbrücken", 49.240, 6.997, "DE", "SL", False),
    ("Freiburg", 47.999, 7.842, "DE", "BW", False),
    ("Heidelberg", 49.399, 8.672, "DE", "BW", False),
    ("Heilbronn", 49.140, 9.220, "DE", "BW", False),
    ("Ulm", 48.401, 9.988, "DE", "BW", False),
    ("Pforzheim", 48.892, 8.694, "DE", "BW", False),
    ("Reutlingen", 48.492, 9.204, "DE", "BW", False),
    ("Konstanz", 47.660, 9.175, "DE", "BW", False),
    ("Tübingen", 48.521, 9.057, "DE", "BW", False),
    ("Ludwigsburg", 48.897, 9.192, "DE", "BW", False),
    ("Offenburg", 48.473, 7.944, "DE", "BW", False),
    ("Baden-Baden", 48.760, 8.240, "DE", "BW", False),
    ("Friedrichshafen", 47.654, 9.480, "DE", "BW", False),
    ("Regensburg", 49.013, 12.102, "DE", "BY", False),
    ("Würzburg", 49.791, 9.953, "DE", "BY", False),
    ("Ingolstadt", 48.763, 11.425, "DE", "BY", False),
    ("Fürth", 49.477, 10.989, "DE", "BY", False),
    ("Erlangen", 49.597, 11.004, "DE", "BY", False),
    ("Bayreuth", 49.948, 11.578, "DE", "BY", False),
    ("Bamberg", 49.892, 10.887, "DE", "BY", False),
    ("Passau", 48.574, 13.431, "DE", "BY", False),
    ("Rosenheim", 47.857, 12.123, "DE", "BY", False),
    ("Kempten", 47.728, 10.316, "DE", "BY", False),
    ("Landshut", 48.538, 12.152, "DE", "BY", False),
    ("Hof", 50.313, 11.912, "DE", "BY", True),
    ("Garmisch-Partenkirchen", 47.492, 11.095, "DE", "BY", False),
    ("Berchtesgaden", 47.631, 13.003, "DE", "BY", False),
    ("Kassel", 51.313, 9.480, "DE", "HE", False),
    ("Darmstadt", 49.872, 8.651, "DE", "HE", False),
    ("Offenbach", 50.095, 8.766, "DE", "HE", False),
    ("Gießen", 50.587, 8.678, "DE", "HE", False),
    ("Marburg", 50.810, 8.771, "DE", "HE", False),
    ("Fulda", 50.552, 9.678, "DE", "HE", False),
    ("Hanau", 50.134, 8.917, "DE", "HE", False),
    ("Oldenburg", 53.143, 8.214, "DE", "NI", False),
    ("Osnabrück", 52.280, 8.047, "DE", "NI", False),
    ("Göttingen", 51.534, 9.935, "DE", "NI", False),
    ("Wolfsburg", 52.423, 10.787, "DE", "NI", False),
    ("Hildesheim", 52.150, 9.951, "DE", "NI", False),
    ("Salzgitter", 52.150, 10.359, "DE", "NI", False),
    ("Lüneburg", 53.249, 10.407, "DE", "NI", False),
    ("Wilhelmshaven", 53.530, 8.107, "DE", "NI", False),
    ("Emden", 53.367, 7.206, "DE", "NI", False),
    ("Cuxhaven", 53.862, 8.694, "DE", "NI", False),
    ("Delmenhorst", 53.051, 8.631, "DE", "NI", False),
    ("Lübeck", 53.866, 10.687, "DE", "SH", False),
    ("Flensburg", 54.783, 9.436, "DE", "SH", False),
    ("Neumünster", 54.073, 9.984, "DE", "SH", False),
    ("Rostock", 54.092, 12.099, "DE", "MV", False),
    ("Schwerin", 53.636, 11.401, "DE", "MV", False),
    ("Stralsund", 54.309, 13.082, "DE", "MV", False),
    ("Greifswald", 54.093, 13.381, "DE", "MV", False),
    ("Neubrandenburg", 53.557, 13.261, "DE", "MV", False),
    ("Wismar", 53.893, 11.465, "DE", "MV", False),
    ("Potsdam", 52.391, 13.065, "DE", "BB", False),
    ("Cottbus", 51.757, 14.329, "DE", "BB", False),
    ("Görlitz", 51.152, 14.987, "DE", "SN", False),
    ("Zwickau", 50.718, 12.492, "DE", "SN", False),
    ("Plauen", 50.497, 12.138, "DE", "SN", False),
    ("Bautzen", 51.181, 14.424, "DE", "SN", False),
    ("Gütersloh", 51.906, 8.378, "DE", "NW", False),
    ("Paderborn", 51.719, 8.754, "DE", "NW", False),
    ("Hagen", 51.361, 7.474, "DE", "NW", True),
    ("Hamm", 51.681, 7.815, "DE", "NW", False),
    ("Herne", 51.538, 7.219, "DE", "NW", False),
    ("Krefeld", 51.339, 6.585, "DE", "NW", False),
    ("Leverkusen", 51.033, 6.985, "DE", "NW", False),
    ("Oberhausen", 51.470, 6.852, "DE", "NW", False),
    ("Mülheim an der Ruhr", 51.431, 6.883, "DE", "NW", False),
    ("Neuss", 51.198, 6.689, "DE", "NW", False),
    ("Solingen", 51.171, 7.083, "DE", "NW", False),
    ("Remscheid", 51.179, 7.193, "DE", "NW", False),
    ("Recklinghausen", 51.614, 7.198, "DE", "NW", False),
    ("Siegen", 50.875, 8.016, "DE", "NW", False),
    ("Bergisch Gladbach", 50.992, 7.129, "DE", "NW", False),
    ("Bottrop", 51.524, 6.929, "DE", "NW", False),
    ("Moers", 51.452, 6.627, "DE", "NW", False),
    ("Witten", 51.443, 7.352, "DE", "NW", False),
    ("Detmold", 51.936, 8.877, "DE", "NW", False),
    ("Bocholt", 51.838, 6.616, "DE", "NW", False),
    # islands / regions often named in reports
    ("Sylt", 54.910, 8.340, "DE", "SH", False),
    ("Helgoland", 54.180, 7.890, "DE", "SH", False),
    ("Fehmarn", 54.440, 11.190, "DE", "SH", False),
    ("Rügen", 54.420, 13.400, "DE", "MV", False),
    ("Usedom", 53.950, 14.050, "DE", "MV", False),
    ("Borkum", 53.590, 6.660, "DE", "NI", False),
    # -- Poland ------------------------------------------------------------
    ("Warschau", 52.230, 21.012, "PL", None, False),
    ("Stettin", 53.428, 14.553, "PL", None, False),
    ("Breslau", 51.108, 17.039, "PL", None, False),
    ("Posen", 52.407, 16.931, "PL", None, False),
    ("Danzig", 54.352, 18.647, "PL", None, False),
    ("Krakau", 50.065, 19.945, "PL", None, False),
    # -- Czechia -----------------------------------------------------------
    ("Prag", 50.075, 14.438, "CZ", None, False),
    ("Brünn", 49.195, 16.608, "CZ", None, False),
    ("Pilsen", 49.748, 13.378, "CZ", None, False),
    ("Karlsbad", 50.231, 12.872, "CZ", None, False),
    # -- Austria -----------------------------------------------------------
    ("Wien", 48.208, 16.373, "AT", None, False),
    ("Salzburg", 47.809, 13.055, "AT", None, False),
    ("Innsbruck", 47.269, 11.404, "AT", None, False),
    ("Graz", 47.070, 15.439, "AT", None, False),
    ("Linz", 48.306, 14.286, "AT", None, False),
    # -- Switzerland -------------------------------------------------------
    ("Zürich", 47.377, 8.540, "CH", None, False),
    ("Basel", 47.559, 7.588, "CH", None, False),
    ("Bern", 46.948, 7.447, "CH", None, False),
    ("Genf", 46.204, 6.143, "CH", None, False),
    # -- France ------------------------------------------------------------
    ("Paris", 48.857, 2.352, "FR", None, False),
    ("Straßburg", 48.573, 7.752, "FR", None, False),
    ("Metz", 49.119, 6.176, "FR", None, False),
    ("Lille", 50.629, 3.057, "FR", None, False),
    # -- Benelux -----------------------------------------------------------
    ("Amsterdam", 52.368, 4.904, "NL", None, False),
    ("Rotterdam", 51.924, 4.478, "NL", None, False),
    ("Den Haag", 52.078, 4.288, "NL", None, False),
    ("Venlo", 51.370, 6.169, "NL", None, False),
    ("Brüssel", 50.850, 4.352, "BE", None, False),
    ("Antwerpen", 51.219, 4.402, "BE", None, False),
    ("Lüttich", 50.633, 5.568, "BE", None, False),
    # -- Denmark / Baltic --------------------------------------------------
    ("Kopenhagen", 55.676, 12.568, "DK", None, False),
    ("Aarhus", 56.163, 10.204, "DK", None, False),
    ("Vilnius", 54.687, 25.280, "LT", None, False),
    ("Riga", 56.950, 24.106, "LV", None, False),
    ("Tallinn", 59.437, 24.754, "EE", None, False),
    ("Kaliningrad", 54.710, 20.451, "RU", None, False),
    # -- Ukraine / Russia (world, relevant for the situation picture) ------
    ("Kiew", 50.450, 30.523, "UA", None, False),
    ("Lwiw", 49.840, 24.030, "UA", None, False),
    ("Charkiw", 49.990, 36.230, "UA", None, False),
    ("Odessa", 46.480, 30.730, "UA", None, False),
    ("Moskau", 55.756, 37.617, "RU", None, False),
)

# Presseportal prefix ("POL-HH:") -> (state, city name from the gazetteer or None).
# Only codes that are certain are listed; anything else falls back to text
# matching. Extend this table rather than guessing.
DIENSTSTELLEN: dict[str, tuple[str, str | None]] = {
    # city states
    "HH": ("HH", "Hamburg"), "B": ("BE", "Berlin"), "HB": ("HB", "Bremen"),
    "BHV": ("HB", "Bremerhaven"),
    # Nordrhein-Westfalen
    "D": ("NW", "Düsseldorf"), "DO": ("NW", "Dortmund"), "E": ("NW", "Essen"),
    "GE": ("NW", "Gelsenkirchen"), "BO": ("NW", "Bochum"), "HA": ("NW", "Hagen"),
    "MS": ("NW", "Münster"), "BI": ("NW", "Bielefeld"), "K": ("NW", "Köln"),
    "BN": ("NW", "Bonn"), "AC": ("NW", "Aachen"), "MG": ("NW", "Mönchengladbach"),
    "W": ("NW", "Wuppertal"), "SG": ("NW", "Solingen"), "RS": ("NW", "Remscheid"),
    "DU": ("NW", "Duisburg"), "OB": ("NW", "Oberhausen"), "MH": ("NW", "Mülheim an der Ruhr"),
    "HAM": ("NW", "Hamm"), "HER": ("NW", "Herne"), "BOT": ("NW", "Bottrop"),
    "KR": ("NW", "Krefeld"), "LEV": ("NW", "Leverkusen"), "NE": ("NW", None),
    "KLE": ("NW", None), "WES": ("NW", None), "RE": ("NW", "Recklinghausen"),
    "COE": ("NW", None), "BOR": ("NW", None), "ST": ("NW", None), "WAF": ("NW", None),
    "VIE": ("NW", None), "GT": ("NW", "Gütersloh"), "PB": ("NW", "Paderborn"),
    "HX": ("NW", None), "LIP": ("NW", None), "MI": ("NW", None), "HF": ("NW", None),
    "GL": ("NW", "Bergisch Gladbach"), "SU": ("NW", None), "EU": ("NW", None),
    "DN": ("NW", None), "HS": ("NW", None), "OE": ("NW", None), "ME": ("NW", None),
    "UN": ("NW", None), "MK": ("NW", None), "SO": ("NW", None), "HSK": ("NW", None),
    "EN": ("NW", None), "SI": ("NW", "Siegen"), "BM": ("NW", None), "GM": ("NW", None),
    # Niedersachsen
    "H": ("NI", "Hannover"), "BS": ("NI", "Braunschweig"), "OL": ("NI", "Oldenburg"),
    "OS": ("NI", "Osnabrück"), "GÖ": ("NI", "Göttingen"), "GOE": ("NI", "Göttingen"),
    "LG": ("NI", "Lüneburg"), "HI": ("NI", "Hildesheim"), "STD": ("NI", None),
    "DEL": ("NI", "Delmenhorst"), "CLP": ("NI", None), "VEC": ("NI", None),
    "EL": ("NI", None), "NOM": ("NI", None), "HM": ("NI", None), "SHG": ("NI", None),
    "NI": ("NI", None), "GF": ("NI", None), "WOB": ("NI", "Wolfsburg"),
    "SZ": ("NI", "Salzgitter"), "WL": ("NI", None), "CE": ("NI", None),
    "DH": ("NI", None), "OHZ": ("NI", None), "ROW": ("NI", None), "VER": ("NI", None),
    "WHV": ("NI", "Wilhelmshaven"), "AUR": ("NI", None), "WTM": ("NI", None),
    "LER": ("NI", None), "NOH": ("NI", None),
    # Schleswig-Holstein
    "FL": ("SH", "Flensburg"), "KI": ("SH", "Kiel"), "HL": ("SH", "Lübeck"),
    "NMS": ("SH", "Neumünster"), "IZ": ("SH", None), "PI": ("SH", None),
    "RZ": ("SH", None), "SE": ("SH", None), "OD": ("SH", None),
    # Mecklenburg-Vorpommern
    "HRO": ("MV", "Rostock"), "NB": ("MV", "Neubrandenburg"),
    # Hessen
    "F": ("HE", "Frankfurt am Main"), "OF": ("HE", "Offenbach"), "DA": ("HE", "Darmstadt"),
    "WI": ("HE", "Wiesbaden"), "KS": ("HE", "Kassel"), "GI": ("HE", "Gießen"),
    "MR": ("HE", "Marburg"), "FD": ("HE", "Fulda"), "HG": ("HE", None),
    "MTK": ("HE", None), "GG": ("HE", None),
    # Baden-Württemberg
    "KA": ("BW", "Karlsruhe"), "S": ("BW", "Stuttgart"), "MA": ("BW", "Mannheim"),
    "HD": ("BW", "Heidelberg"), "HN": ("BW", "Heilbronn"), "FR": ("BW", "Freiburg"),
    "OG": ("BW", "Offenburg"), "KN": ("BW", "Konstanz"), "RT": ("BW", "Reutlingen"),
    "UL": ("BW", "Ulm"), "RV": ("BW", None), "AA": ("BW", None), "LB": ("BW", "Ludwigsburg"),
    "GP": ("BW", None), "ES": ("BW", None), "BB": ("BW", None), "PF": ("BW", "Pforzheim"),
    "TUT": ("BW", None), "FN": ("BW", "Friedrichshafen"),
    # Bayern
    "MFR": ("BY", None), "OFR": ("BY", None), "UFR": ("BY", None), "OPF": ("BY", None),
    "OBN": ("BY", None), "OBS": ("BY", None),
    # Sachsen
    "DD": ("SN", "Dresden"), "L": ("SN", "Leipzig"), "C": ("SN", "Chemnitz"),
    "Z": ("SN", "Zwickau"), "GR": ("SN", "Görlitz"),
    # Sachsen-Anhalt
    "MD": ("ST", "Magdeburg"), "HAL": ("ST", "Halle (Saale)"), "DE": ("ST", "Dessau-Roßlau"),
}

# Whole families of codes: Rheinland-Pfalz uses PP*/PD* (e.g. POL-PPMZ),
# Thüringen uses the LPI- prefix (e.g. LPI-EF).
_STATE_BY_CODE_PREFIX: tuple[tuple[str, str], ...] = (("PP", "RP"), ("PD", "RP"))
_STATE_BY_KIND: dict[str, str] = {"LPI": "TH"}

# ---------------------------------------------------------------------------
# Germany outline (coarse, clockwise, lat/lon) and neighbourhood
# ---------------------------------------------------------------------------

GERMANY_POLYGON: tuple[tuple[float, float], ...] = (
    # North Sea coast (islands included) and Danish border
    (53.75, 6.45), (53.90, 7.30), (54.20, 7.70), (54.75, 8.20), (55.08, 8.40),
    (54.92, 8.62), (54.87, 8.95), (54.82, 9.40), (54.82, 9.80), (54.80, 10.05),
    # Baltic coast
    (54.70, 10.60), (54.60, 11.10), (54.45, 11.35), (54.15, 11.20), (54.00, 10.90),
    (53.95, 11.40), (54.05, 12.00), (54.35, 12.50), (54.55, 13.10), (54.70, 13.75),
    (54.30, 14.00), (54.05, 14.20), (53.93, 14.23), (53.85, 14.22),
    # Polish border (Oder / Neisse)
    (53.50, 14.20), (53.05, 14.40), (52.55, 14.70), (52.10, 14.72), (51.95, 14.78),
    (51.50, 14.80), (51.10, 15.05), (50.90, 15.00),
    # Czech border
    (50.80, 14.55), (50.88, 14.30), (50.70, 13.90), (50.45, 13.10), (50.35, 12.50),
    (50.25, 12.10), (50.00, 12.20), (49.70, 12.60), (49.30, 12.80), (49.05, 13.25),
    (48.80, 13.85),
    # Austrian border
    (48.57, 13.80), (48.30, 13.05), (47.95, 12.92), (47.70, 12.95), (47.55, 13.10),
    (47.60, 12.19), (47.45, 11.40), (47.45, 10.90), (47.30, 10.25), (47.55, 10.00),
    (47.52, 9.70),
    # Lake Constance / Swiss border / Rhine
    (47.58, 9.55), (47.65, 9.20), (47.70, 8.70), (47.62, 8.20), (47.58, 7.60),
    # French border / Rhine / Saarland / Pfalz
    (47.90, 7.55), (48.35, 7.70), (48.58, 7.78), (48.85, 8.20), (48.97, 8.22), (49.05, 7.80),
    (49.15, 7.05), (49.20, 6.50),
    # Luxembourg, Belgian and Dutch borders
    (49.50, 6.35), (49.85, 6.37), (50.30, 6.35), (50.55, 6.17), (50.80, 5.98),
    (51.05, 5.87), (51.35, 6.18), (51.80, 6.05), (51.85, 6.40), (52.20, 6.90),
    (52.60, 7.05), (53.00, 7.20), (53.30, 7.10), (53.45, 6.75),
)

# "Umgebung": Germany's bounding box widened by this many degrees (~200-330 km).
NEIGHBORHOOD_MARGIN_DEG = 3.0
_GERMANY_BBOX_LONLAT = (5.5, 47.0, 15.6, 55.2)  # min_lon, min_lat, max_lon, max_lat


def in_germany(lat: float, lon: float) -> bool:
    """True when the point lies inside the coarse Germany outline."""
    inside = False
    n = len(GERMANY_POLYGON)
    for i in range(n):
        lat1, lon1 = GERMANY_POLYGON[i]
        lat2, lon2 = GERMANY_POLYGON[(i + 1) % n]
        if (lat1 > lat) != (lat2 > lat):
            cross_lon = (lon2 - lon1) * (lat - lat1) / (lat2 - lat1) + lon1
            if lon < cross_lon:
                inside = not inside
    return inside


def in_neighborhood(lat: float, lon: float) -> bool:
    """True when the point is in the wider area around Germany (incl. Germany)."""
    min_lon, min_lat, max_lon, max_lat = _GERMANY_BBOX_LONLAT
    margin = NEIGHBORHOOD_MARGIN_DEG
    return (
        min_lat - margin <= lat <= max_lat + margin
        and min_lon - margin <= lon <= max_lon + margin
    )


def region_of_point(lat: float, lon: float) -> str:
    """Return "de", "near_abroad" or "world" for a coordinate."""
    if in_germany(lat, lon):
        return "de"
    return "near_abroad" if in_neighborhood(lat, lon) else "world"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Place matching
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Place:
    """One gazetteer entry."""

    name: str
    lat: float
    lon: float
    country: str
    state: str | None
    kind: str  # "city" | "state" | "country"
    ambiguous: bool = False


@dataclass(frozen=True, slots=True)
class GeoMatch:
    """Best location found for a text."""

    lat: float
    lon: float
    precision: str  # "city" | "state" | "country"
    name: str
    country: str
    state: str | None
    source: str  # "dateline" | "title" | "dienststelle" | "text" | "state" | "country"

    @property
    def label(self) -> str:
        return {
            "city": "News mit Ortsbezug",
            "state": "Bundesland (ungefähr)",
            "country": "Land (ungefähr)",
        }[self.precision]


_PLACES: list[Place] = []
_BY_KEY: dict[str, Place] = {}


def _register(place: Place, *names: str) -> None:
    _PLACES.append(place)
    for name in names:
        for key in {fold(name), fold_plain(name)}:
            _BY_KEY.setdefault(key, place)


for _name, _lat, _lon, _country, _state, _amb in _CITY_ROWS:
    _register(Place(_name, _lat, _lon, _country, _state, "city", _amb), _name)

for _code, (_sname, _lat, _lon) in STATES.items():
    if STATE_ALIASES.get(_code):
        _register(Place(_sname, _lat, _lon, "DE", _code, "state"), _sname, *STATE_ALIASES[_code])

for _code, (_cname, _lat, _lon) in COUNTRIES.items():
    _register(Place(_cname, _lat, _lon, _code, None, "country"), _cname, *COUNTRY_ALIASES.get(_code, ()))

# Sachsen must not swallow "Sachsen-Anhalt": longest alternatives are tried first.
_ALTERNATIVES = sorted(_BY_KEY, key=len, reverse=True)
_PREPOSITIONS = r"(?:in|aus|bei|nach|von|nahe|bis|um|ab)"
_NAME_RE = re.compile(
    r"(?<![a-z0-9])(?P<name>" + "|".join(re.escape(k) for k in _ALTERNATIVES) + r")(?P<suffix>er)?(?![a-z0-9])"
)
_PREP_BEFORE_RE = re.compile(_PREPOSITIONS + r"\s+$")


def find_places(text: str) -> list[tuple[int, Place]]:
    """Return (position, place) for all gazetteer hits, in order of appearance.

    Matching works on folded text with word boundaries, so "Interessen" no
    longer matches Essen. Ambiguous names (Essen, Halle, Hof, Hagen) only
    count after a preposition ("in Essen") or at the start ("Essen: ...").
    """
    results: list[tuple[int, Place]] = []
    for variant in {fold(text), fold_plain(text)}:
        for match in _NAME_RE.finditer(variant):
            place = _BY_KEY[match.group("name")]
            if match.group("suffix") and place.kind != "city":
                continue  # "bayerner" is not a thing; only city adjectives (Kölner)
            if place.ambiguous and not _is_preceded_by_preposition(variant, match.start()):
                continue
            results.append((match.start(), place))
        if results:
            break  # the first folding that yields hits is enough
    results.sort(key=lambda pair: pair[0])
    return results


def _is_preceded_by_preposition(text: str, start: int) -> bool:
    if start == 0:
        return True
    before = text[max(0, start - 12):start]
    return bool(_PREP_BEFORE_RE.search(before)) or before.rstrip().endswith((":", "-"))


def count_by_country(text: str) -> dict[str, int]:
    """Number of gazetteer hits per country code (states count as DE)."""
    counts: dict[str, int] = {}
    for _pos, place in find_places(text):
        counts[place.country] = counts.get(place.country, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Presseportal prefixes and datelines
# ---------------------------------------------------------------------------

_PREFIX_RE = re.compile(r"^\s*(?P<kind>[A-Za-z]{2,5})[-\s](?P<code>[A-Za-zÄÖÜäöüß]{1,5}?)\s*:")
_DATELINE_RE = re.compile(r"^\s*(?P<place>[^()\n]{2,60}?)\s*\(ots\)", re.IGNORECASE)


def parse_dienststelle(title: str) -> tuple[str, str | None] | None:
    """Return (state, city name or None) for a Presseportal prefix like "POL-HH:"."""
    match = _PREFIX_RE.match(title or "")
    if not match:
        return None
    kind = match.group("kind").upper()
    code = match.group("code").upper()
    if kind in _STATE_BY_KIND:
        return _STATE_BY_KIND[kind], None
    if kind != "POL":
        return None
    if code in DIENSTSTELLEN:
        return DIENSTSTELLEN[code]
    for prefix, state in _STATE_BY_CODE_PREFIX:
        if len(code) >= 3 and code.startswith(prefix):
            return state, None
    return None


def parse_dateline(summary: str) -> str | None:
    """Return the place of an "Ort (ots) - ..." dateline, if present."""
    match = _DATELINE_RE.match(summary or "")
    return match.group("place").strip() if match else None


def _city_by_name(name: str) -> Place | None:
    place = _BY_KEY.get(fold(name)) or _BY_KEY.get(fold_plain(name))
    return place if place and place.kind == "city" else None


def _match_from_place(place: Place, precision: str, source: str) -> GeoMatch:
    return GeoMatch(place.lat, place.lon, precision, place.name, place.country, place.state, source)


def locate(title: str, summary: str = "") -> GeoMatch | None:
    """Best-effort location of a news item.

    Priority: dateline > city in title > Dienststelle city > city in summary >
    Dienststelle state > state/country in text.
    """
    dateline = parse_dateline(summary)
    if dateline:
        for _pos, place in find_places(dateline):
            if place.kind == "city":
                return _match_from_place(place, "city", "dateline")

    title_hits = find_places(title)
    for _pos, place in title_hits:
        if place.kind == "city":
            return _match_from_place(place, "city", "title")

    dienst = parse_dienststelle(title)
    if dienst and dienst[1]:
        city = _city_by_name(dienst[1])
        if city:
            return _match_from_place(city, "city", "dienststelle")

    summary_hits = find_places(summary)
    for _pos, place in summary_hits:
        if place.kind == "city":
            return _match_from_place(place, "city", "text")

    if dienst:
        name, lat, lon = STATES[dienst[0]]
        return GeoMatch(lat, lon, "state", name, "DE", dienst[0], "dienststelle")

    for _pos, place in (*title_hits, *summary_hits):
        if place.kind == "state":
            return _match_from_place(place, "state", "state")
    for _pos, place in (*title_hits, *summary_hits):
        if place.kind == "country":
            return _match_from_place(place, "country", "country")
    return None


def state_for_point(lat: float, lon: float, max_km: float = 80.0) -> str | None:
    """Bundesland of a point using the nearest German gazetteer city.

    Approximate near state borders; returns None when no city is within
    ``max_km`` or the point is outside Germany.
    """
    if not in_germany(lat, lon):
        return None
    best: tuple[float, str] | None = None
    for place in _PLACES:
        if place.kind != "city" or place.country != "DE" or not place.state:
            continue
        distance = haversine_km(lat, lon, place.lat, place.lon)
        if best is None or distance < best[0]:
            best = (distance, place.state)
    return best[1] if best and best[0] <= max_km else None
