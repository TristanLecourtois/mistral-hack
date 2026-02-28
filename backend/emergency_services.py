import json
import math
import requests
import os

# ── Haversine distance (km) ──────────────────────────────────────────────────

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# ── Loaders ──────────────────────────────────────────────────────────────────

def load_police_stations() -> list[dict]:
    path = os.path.join(os.path.dirname(__file__), "../data/police.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        stations = []
        for record in data:
            fields = record.get("fields", {})
            coords = fields.get("wgs84", [])
            if len(coords) == 2:
                stations.append({
                    "lat":     coords[0],
                    "lng":     coords[1],
                    "name":    fields.get("service", "Commissariat"),
                    "address": fields.get("adresse", ""),
                    "phone":   fields.get("telephone", ""),
                    "hours":   fields.get("horaires", ""),
                    "type":    "police",
                })
        print(f"[SERVICES] {len(stations)} commissariats chargés")
        return stations
    except Exception as e:
        print(f"[SERVICES] Erreur chargement police.json: {e}")
        return []


def fetch_fire_stations() -> list[dict]:
    query = """
    [out:json];
    (
      node["amenity"="fire_station"](48.70,2.20,49.00,2.60);
      way["amenity"="fire_station"](48.70,2.20,49.00,2.60);
    );
    out center;
    """
    try:
        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=query,
            timeout=20,
        )
        elements = response.json().get("elements", [])
        stations = []
        for el in elements:
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat and lon:
                tags = el.get("tags", {})
                stations.append({
                    "lat":     lat,
                    "lng":     lon,
                    "name":    tags.get("name", "Caserne de pompiers"),
                    "address": tags.get("addr:street", ""),
                    "phone":   tags.get("phone", ""),
                    "hours":   "",
                    "type":    "fire",
                })
        print(f"[SERVICES] {len(stations)} casernes de pompiers chargées via Overpass")
        return stations
    except Exception as e:
        print(f"[SERVICES] Erreur Overpass API: {e}")
        return []


def fetch_hospitals() -> list[dict]:
    query = """
    [out:json];
    (
      node["amenity"="hospital"](48.70,2.20,49.00,2.60);
      way["amenity"="hospital"](48.70,2.20,49.00,2.60);
    );
    out center;
    """
    try:
        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=query,
            timeout=20,
        )
        elements = response.json().get("elements", [])
        hospitals = []
        for el in elements:
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat and lon:
                tags = el.get("tags", {})
                hospitals.append({
                    "lat":     lat,
                    "lng":     lon,
                    "name":    tags.get("name", "Hôpital"),
                    "address": tags.get("addr:street", ""),
                    "phone":   tags.get("phone", ""),
                    "hours":   "",
                    "type":    "hospital",
                })
        print(f"[SERVICES] {len(hospitals)} hôpitaux chargés via Overpass")
        return hospitals
    except Exception as e:
        print(f"[SERVICES] Erreur Overpass API hospitals: {e}")
        return []


# ── Find nearest ─────────────────────────────────────────────────────────────

def find_nearest(lat: float, lng: float, call_type: str, registry: dict) -> dict | None:
    stations = registry.get(call_type, [])
    if not stations:
        return None
    nearest = min(stations, key=lambda s: haversine(lat, lng, s["lat"], s["lng"]))
    dist = haversine(lat, lng, nearest["lat"], nearest["lng"])
    return {**nearest, "distance_km": round(dist, 2)}


# ── Route OSRM ───────────────────────────────────────────────────────────────

def get_route(lat1: float, lng1: float, lat2: float, lng2: float) -> list | None:
    """
    Retourne l'itinéraire réel entre deux points via OSRM (gratuit, sans clé).
    Format retourné : [[lat, lng], ...] pour Leaflet.
    """
    try:
        url = (
            f"http://router.project-osrm.org/route/v1/driving/"
            f"{lng1},{lat1};{lng2},{lat2}"
            f"?overview=full&geometries=geojson"
        )
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("code") == "Ok":
            coords = data["routes"][0]["geometry"]["coordinates"]
            return [[c[1], c[0]] for c in coords]  # GeoJSON [lng,lat] → Leaflet [lat,lng]
        return None
    except Exception as e:
        print(f"Erreur OSRM: {e}")
        return None


# ── Registry (chargé une seule fois au démarrage) ────────────────────────────

def build_registry() -> dict:
    return {
        "police":   load_police_stations(),
        "fire":     fetch_fire_stations(),
        "hospital": fetch_hospitals(),
    }
