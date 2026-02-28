import googlemaps

GOOGLE_API_KEY = "AIzaSyDix0E1Y6refMWcgt-GAdlq3hjg0PB98HI"

_gmaps = googlemaps.Client(key=GOOGLE_API_KEY)


def geocode(address: str) -> dict | None:
    """
    Convertit une adresse en coordonnées GPS via Google Maps.
    Retourne {"lat": float, "lng": float, "formatted_address": str} ou None.
    """
    try:
        results = _gmaps.geocode(address)
        if not results:
            print(f"[GEOCODE] Aucun résultat pour '{address}'")
            return None
        loc = results[0]["geometry"]["location"]
        return {
            "lat": loc["lat"],
            "lng": loc["lng"],
            "formatted_address": results[0]["formatted_address"],
        }
    except Exception as e:
        print(f"[GEOCODE] Erreur: {e}")
        return None


def street_view_url(lat: float, lng: float, width: int = 400, height: int = 220) -> str:
    """
    Retourne l'URL directe de l'image Google Street View.
    Utilisable directement comme <img src="...">.
    """
    return (
        f"https://maps.googleapis.com/maps/api/streetview"
        f"?size={width}x{height}&location={lat},{lng}&key={GOOGLE_API_KEY}"
    )