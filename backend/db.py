from datetime import datetime, timedelta
import random

# Sample database for 911 calls
calls_db = {}


def generate_sample_data():
    sample_data = [
        {
            "id": "1",
            "time": (datetime.now() - timedelta(minutes=random.randint(5, 40))).isoformat(),
            "transcript": [
                {"role": "assistant", "content": "9-1-1, what's your emergency?"},
                {"role": "user", "content": "There's a fire on the third floor of my building, smoke everywhere!"},
                {"role": "assistant", "content": "Is anyone trapped inside?"},
                {"role": "user", "content": "I don't know, I got out but my neighbor might still be in there!"},
            ],
            "emotions": [
                {"emotion": "fear", "intensity": 0.85},
                {"emotion": "panic", "intensity": 0.75},
                {"emotion": "urgency", "intensity": 0.95},
            ],
            "phone": "06 12 34 56 78",
            "recommendation": "Evacuate immediately. Do not use elevators. Close doors to slow fire spread.",
            "severity": "CRITICAL",
            "type": "fire",
            "name": "Marc Dupont",
            "title": "Building Fire in Le Marais",
            "summary": "Caller reported a fire on the third floor of an apartment building in Le Marais. Possible trapped resident.",
            "location_name": "17 Rue du Temple, 75004 Paris",
            "coordinates": {"lat": 48.8573, "lng": 2.3535},
            "scores": {"anxiety": 8, "coherence": 6, "severity_score": 9, "seriousness": 9, "proximity_to_victim": 7},
            "street_image": "https://maps.googleapis.com/maps/api/streetview?size=400x220&location=48.8573,2.3535&key=AIzaSyDix0E1Y6refMWcgt-GAdlq3hjg0PB98HI",
        },
        {
            "id": "2",
            "time": (datetime.now() - timedelta(minutes=random.randint(10, 60))).isoformat(),
            "transcript": [
                {"role": "assistant", "content": "9-1-1, what's your emergency?"},
                {"role": "user", "content": "My husband collapsed, he's not responding, I think it's a cardiac arrest!"},
                {"role": "assistant", "content": "Is he breathing?"},
                {"role": "user", "content": "No, I don't think so, please hurry!"},
            ],
            "emotions": [
                {"emotion": "panic", "intensity": 0.97},
                {"emotion": "desperation", "intensity": 0.92},
                {"emotion": "helplessness", "intensity": 0.80},
            ],
            "phone": "06 98 76 54 32",
            "recommendation": "Begin CPR immediately — 30 chest compressions then 2 rescue breaths. Do not stop.",
            "severity": "CRITICAL",
            "type": "hospital",
            "name": "Sophie Bernard",
            "title": "Cardiac Arrest near Arc de Triomphe",
            "summary": "Caller's husband collapsed and is unresponsive. Suspected cardiac arrest. CPR guidance in progress.",
            "location_name": "5 Avenue de la Grande Armée, 75017 Paris",
            "coordinates": {"lat": 48.8762, "lng": 2.2965},
            "scores": {"anxiety": 10, "coherence": 4, "severity_score": 10, "seriousness": 10, "proximity_to_victim": 10},
            "street_image": "https://maps.googleapis.com/maps/api/streetview?size=400x220&location=48.8762,2.2965&key=AIzaSyDix0E1Y6refMWcgt-GAdlq3hjg0PB98HI",
        },
        {
            "id": "3",
            "time": (datetime.now() - timedelta(minutes=random.randint(2, 25))).isoformat(),
            "transcript": [
                {"role": "assistant", "content": "9-1-1, what's your emergency?"},
                {"role": "user", "content": "Someone just broke the window of a pharmacy, they're inside robbing it!"},
                {"role": "assistant", "content": "Are you safe? What is the exact address?"},
                {"role": "user", "content": "Yes I'm across the street. It's on Rue de la Roquette, near the corner with Rue Servan."},
            ],
            "emotions": [
                {"emotion": "fear", "intensity": 0.65},
                {"emotion": "alertness", "intensity": 0.88},
                {"emotion": "anxiety", "intensity": 0.55},
            ],
            "phone": "06 24 68 13 57",
            "recommendation": "Do not approach. Stay hidden and observe. Keep the line open.",
            "severity": "MODERATE",
            "type": "police",
            "name": "Julien Martin",
            "title": "Pharmacy Robbery on Rue de la Roquette",
            "summary": "Caller witnessed an ongoing break-in at a pharmacy near Bastille. Suspects still inside.",
            "location_name": "42 Rue de la Roquette, 75011 Paris",
            "coordinates": {"lat": 48.8529, "lng": 2.3745},
            "scores": {"anxiety": 5, "coherence": 9, "severity_score": 6, "seriousness": 7, "proximity_to_victim": 2},
            "street_image": "https://maps.googleapis.com/maps/api/streetview?size=400x220&location=48.8529,2.3745&key=AIzaSyDix0E1Y6refMWcgt-GAdlq3hjg0PB98HI",
        },
        {
            "id": "4",
            "time": (datetime.now() - timedelta(minutes=random.randint(15, 80))).isoformat(),
            "transcript": [
                {"role": "assistant", "content": "9-1-1, what's your emergency?"},
                {"role": "user", "content": "There's been a serious collision on the bridge, at least three cars!"},
                {"role": "assistant", "content": "Are there any injuries?"},
                {"role": "user", "content": "Yes, one person is out of the car and not moving, others seem conscious."},
            ],
            "emotions": [
                {"emotion": "shock", "intensity": 0.82},
                {"emotion": "concern", "intensity": 0.88},
                {"emotion": "distress", "intensity": 0.70},
            ],
            "phone": "06 36 92 58 01",
            "recommendation": "Do not move injured persons. Secure the scene and activate hazard signals.",
            "severity": "CRITICAL",
            "type": "hospital",
            "name": "Camille Leroy",
            "title": "Multi-vehicle Crash on Pont de l'Alma",
            "summary": "Three-car collision on Pont de l'Alma. One person unconscious on ground, others with minor injuries.",
            "location_name": "Pont de l'Alma, 75008 Paris",
            "coordinates": {"lat": 48.8637, "lng": 2.3018},
            "scores": {"anxiety": 7, "coherence": 7, "severity_score": 8, "seriousness": 8, "proximity_to_victim": 3},
            "street_image": "https://maps.googleapis.com/maps/api/streetview?size=400x220&location=48.8637,2.3018&key=AIzaSyDix0E1Y6refMWcgt-GAdlq3hjg0PB98HI",
        },
        {
            "id": "5",
            "time": (datetime.now() - timedelta(minutes=random.randint(3, 20))).isoformat(),
            "transcript": [
                {"role": "assistant", "content": "9-1-1, what's your emergency?"},
                {"role": "user", "content": "I can smell gas very strongly in my apartment, it's overwhelming."},
                {"role": "assistant", "content": "Do not turn on any lights or switches. What is your address?"},
                {"role": "user", "content": "8 Rue Mouffetard, fifth floor."},
            ],
            "emotions": [
                {"emotion": "worry", "intensity": 0.72},
                {"emotion": "uncertainty", "intensity": 0.55},
                {"emotion": "alertness", "intensity": 0.85},
            ],
            "phone": "06 14 72 58 96",
            "recommendation": "Leave immediately without using elevator. Leave door open. Do not use any electrical switches.",
            "severity": "MODERATE",
            "type": "fire",
            "name": "Isabelle Petit",
            "title": "Gas Leak on Rue Mouffetard",
            "summary": "Strong gas smell reported on 5th floor apartment on Rue Mouffetard. Evacuation in progress.",
            "location_name": "8 Rue Mouffetard, 75005 Paris",
            "coordinates": {"lat": 48.8437, "lng": 2.3503},
            "scores": {"anxiety": 6, "coherence": 8, "severity_score": 7, "seriousness": 6, "proximity_to_victim": 10},
            "street_image": "https://maps.googleapis.com/maps/api/streetview?size=400x220&location=48.8437,2.3503&key=AIzaSyDix0E1Y6refMWcgt-GAdlq3hjg0PB98HI",
        },
        {
            "id": "6",
            "time": (datetime.now() - timedelta(minutes=random.randint(1, 15))).isoformat(),
            "transcript": [
                {"role": "assistant", "content": "9-1-1, what's your emergency?"},
                {"role": "user", "content": "There's a man acting very strangely near the school gate, he's been there for 30 minutes watching the kids."},
                {"role": "assistant", "content": "Can you describe him?"},
                {"role": "user", "content": "Tall, dark jacket, backpack, he keeps looking at the children leaving."},
            ],
            "emotions": [
                {"emotion": "suspicion", "intensity": 0.80},
                {"emotion": "concern", "intensity": 0.85},
                {"emotion": "unease", "intensity": 0.72},
            ],
            "phone": "06 95 17 53 28",
            "recommendation": "Alert school staff immediately. Do not approach the suspect. Stay on the line.",
            "severity": "MODERATE",
            "type": "police",
            "name": "Nathalie Girard",
            "title": "Suspicious Individual near École Jules Ferry",
            "summary": "Suspicious man observed near school gate on Canal Saint-Martin for over 30 minutes, watching children.",
            "location_name": "Place Jules Ferry, 75011 Paris",
            "coordinates": {"lat": 48.8699, "lng": 2.3665},
            "scores": {"anxiety": 4, "coherence": 9, "severity_score": 4, "seriousness": 5, "proximity_to_victim": 2},
            "street_image": "https://maps.googleapis.com/maps/api/streetview?size=400x220&location=48.8699,2.3665&key=AIzaSyDix0E1Y6refMWcgt-GAdlq3hjg0PB98HI",
        },
        {
            "id": "7",
            "time": (datetime.now() - timedelta(minutes=random.randint(1, 8))).isoformat(),
            "transcript": [
                {"role": "assistant", "content": "9-1-1, what's your emergency?"},
                {"role": "user", "content": "My son is choking he can't breathe please help!"},
                {"role": "assistant", "content": "How old is he? Is he conscious?"},
                {"role": "user", "content": "He's four, he's turning blue, I don't know what to do!"},
            ],
            "emotions": [
                {"emotion": "panic", "intensity": 0.98},
                {"emotion": "fear", "intensity": 0.95},
                {"emotion": "desperation", "intensity": 0.90},
            ],
            "phone": "06 75 39 51 46",
            "recommendation": "Perform 5 back blows between shoulder blades, then 5 abdominal thrusts. Repeat until clear.",
            "severity": "CRITICAL",
            "type": "hospital",
            "name": "Thomas Roux",
            "title": "Child Choking Emergency in 7th Arr.",
            "summary": "4-year-old child choking and turning blue in Invalides area. Father on line, guidance in progress.",
            "location_name": "31 Avenue Bosquet, 75007 Paris",
            "coordinates": {"lat": 48.8582, "lng": 2.3051},
            "scores": {"anxiety": 10, "coherence": 3, "severity_score": 10, "seriousness": 10, "proximity_to_victim": 10},
            "street_image": "https://maps.googleapis.com/maps/api/streetview?size=400x220&location=48.8582,2.3051&key=AIzaSyDix0E1Y6refMWcgt-GAdlq3hjg0PB98HI",
        },
    ]

    for call in sample_data:
        calls_db[call["id"]] = call


# Generate sample data
generate_sample_data()


def get_all_calls():
    """
    Accessor function to get all calls in the database.
    """
    return calls_db


def get_call(call_id):
    """
    Accessor function to get a specific call by its ID.
    """
    return calls_db.get(call_id, {})


def update_call(call_id, updated_data):
    """
    Modification function to update or insert a specific call's data.
    """
    if call_id in calls_db:
        calls_db[call_id].update(updated_data)
    else:
        calls_db[call_id] = updated_data
    return True


def delete_call(call_id):
    """
    Function to delete a call from the database.
    """
    if call_id in calls_db:
        del calls_db[call_id]
        return True
    return False
