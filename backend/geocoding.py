import requests


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def geocode(address: str) -> dict | None:
    """
    Convertit une adresse en coordonnées GPS via Nominatim (OpenStreetMap).
    Retourne {"lat": float, "lng": float, "formatted_address": str} ou None.
    """
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "hackathon-911-dispatcher"},
            timeout=10,
        )
        data = response.json()
        if not data:
            print(f"Nominatim: aucun résultat pour '{address}'")
            return None
        return {
            "lat": float(data[0]["lat"]),
            "lng": float(data[0]["lon"]),
            "formatted_address": data[0]["display_name"],
        }
    except Exception as e:
        print(f"Erreur geocoding: {e}")
        return None
