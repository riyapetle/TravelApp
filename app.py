import streamlit as st
from groq import Groq
from huggingface_hub import InferenceClient
from concurrent.futures import ThreadPoolExecutor, as_completed
import io, base64, re, requests, textwrap, random, os
from fpdf import FPDF
from PIL import Image
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

# ─── API Keys (Streamlit Cloud secrets → local .env fallback) ───
def get_secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, "")

GROQ_API_KEY = get_secret("GROQ_API_KEY")
HF_API_KEY   = get_secret("HF_API_KEY")

# ─── Country → Cities Data ───
COUNTRY_CITIES = {
    "India": ["Agra","Ahmedabad","Amritsar","Aurangabad","Bengaluru","Bhopal","Bhubaneswar","Chandigarh","Chennai","Coimbatore","Darjeeling","Dehradun","Delhi","Goa (Panaji)","Guwahati","Hyderabad","Indore","Jaipur","Jodhpur","Kochi","Kolkata","Leh","Lucknow","Ludhiana","Madurai","Manali","Mumbai","Mysuru","Nagpur","Patna","Puducherry","Pune","Raipur","Ranchi","Rishikesh","Shillong","Shimla","Srinagar","Surat","Udaipur","Vadodara","Varanasi","Vijayawada","Visakhapatnam"],
    "United States": ["Atlanta","Austin","Boston","Chicago","Dallas","Denver","Honolulu","Houston","Las Vegas","Los Angeles","Miami","Nashville","New Orleans","New York City","Orlando","Philadelphia","Phoenix","Portland","San Diego","San Francisco","Seattle","Washington D.C."],
    "United Kingdom": ["Bath","Birmingham","Brighton","Bristol","Cambridge","Edinburgh","Glasgow","Leeds","Liverpool","London","Manchester","Oxford"],
    "Australia": ["Adelaide","Brisbane","Cairns","Canberra","Darwin","Gold Coast","Hobart","Melbourne","Perth","Sydney"],
    "Canada": ["Calgary","Halifax","Montreal","Ottawa","Quebec City","Toronto","Vancouver","Victoria","Winnipeg"],
    "France": ["Bordeaux","Cannes","Lille","Lyon","Marseille","Monaco","Nice","Paris","Strasbourg","Toulouse"],
    "Germany": ["Berlin","Cologne","Dresden","Frankfurt","Hamburg","Heidelberg","Munich","Nuremberg","Stuttgart"],
    "Italy": ["Amalfi","Bologna","Florence","Genoa","Milan","Naples","Palermo","Rome","Turin","Venice"],
    "Spain": ["Barcelona","Bilbao","Granada","Ibiza","Madrid","Malaga","Palma","Salamanca","Seville","Valencia"],
    "Japan": ["Fukuoka","Hiroshima","Kyoto","Nara","Osaka","Sapporo","Tokyo","Yokohama"],
    "Thailand": ["Bangkok","Chiang Mai","Chiang Rai","Hua Hin","Koh Samui","Krabi","Pattaya","Phuket"],
    "Indonesia": ["Bali (Denpasar)","Bandung","Jakarta","Lombok","Makassar","Medan","Surabaya","Yogyakarta"],
    "Singapore": ["Singapore"],
    "Malaysia": ["George Town","Ipoh","Johor Bahru","Kota Kinabalu","Kuala Lumpur","Langkawi","Malacca"],
    "Vietnam": ["Da Lat","Da Nang","Hanoi","Ho Chi Minh City","Hoi An","Hue","Nha Trang"],
    "Nepal": ["Kathmandu","Lumbini","Pokhara"],
    "Sri Lanka": ["Colombo","Galle","Jaffna","Kandy","Nuwara Eliya"],
    "United Arab Emirates": ["Abu Dhabi","Dubai","Sharjah"],
    "Turkey": ["Ankara","Antalya","Bodrum","Cappadocia","Istanbul","Izmir","Trabzon"],
    "Greece": ["Athens","Corfu","Heraklion","Mykonos","Rhodes","Santorini","Thessaloniki"],
    "Portugal": ["Algarve","Braga","Coimbra","Faro","Lisbon","Porto"],
    "Netherlands": ["Amsterdam","Delft","Eindhoven","Rotterdam","The Hague","Utrecht"],
    "Switzerland": ["Basel","Bern","Geneva","Interlaken","Lausanne","Lucerne","Zurich"],
    "South Africa": ["Cape Town","Durban","Johannesburg","Port Elizabeth","Pretoria"],
    "Egypt": ["Alexandria","Aswan","Cairo","Hurghada","Luxor","Sharm el-Sheikh"],
    "Morocco": ["Agadir","Casablanca","Fez","Marrakech","Rabat","Tangier"],
    "Brazil": ["Brasília","Fortaleza","Manaus","Recife","Rio de Janeiro","Salvador","São Paulo"],
    "Mexico": ["Cancún","Guadalajara","Mexico City","Monterrey","Oaxaca","Puebla","Tulum"],
    "New Zealand": ["Auckland","Christchurch","Dunedin","Hamilton","Queenstown","Wellington"],
    "South Korea": ["Busan","Gyeongju","Incheon","Jeonju","Seoul"],
    "China": ["Beijing","Chengdu","Chongqing","Guangzhou","Guilin","Hangzhou","Shanghai","Shenzhen","Xi'an"],
    "Russia": ["Irkutsk","Kazan","Moscow","Novosibirsk","Saint Petersburg","Sochi","Vladivostok"],
    "Bangladesh": ["Chittagong","Cox's Bazar","Dhaka","Sylhet"],
    "Pakistan": ["Islamabad","Karachi","Lahore","Multan","Peshawar"],
}

ALL_COUNTRIES = sorted(COUNTRY_CITIES.keys())

# ─── App Config ───
st.set_page_config(page_title="Student Travel Planner", layout="wide")

# Inject Color Hunt Palette Theme (#8A7650, #8E977D, #ECE7D1, #DBCEA5)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700;800;900&family=Inter:wght@300;400;500;600;700&display=swap');

:root {
    --bronze: #8A7650;
    --sage: #8E977D;
    --cream: #ECE7D1;
    --tan: #DBCEA5;
    --text-dark: #4A3F2F;
    --text-mid: #6B5D48;
    --text-light: #8A7650;
    --bg-main: #ECE7D1;
    --glass-bg: rgba(255, 255, 255, 0.5);
    --glass-border: rgba(138, 118, 80, 0.25);
}

html, body, [class*="st-"], .stMarkdown, .stText, p, li, label, span, div {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    color: #3A2E1F !important;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Playfair Display', serif !important;
}

label {
    font-weight: 700 !important;
    color: #3A2E1F !important;
}

/* ─── Override Streamlit internal theme colors ─── */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
[data-testid="stToolbar"], [data-testid="stDecoration"],
.main, .main .block-container,
section[data-testid="stSidebar"],
[data-testid="stAppViewBlockContainer"] {
    background-color: #ECE7D1 !important;
    color: #3A2E1F !important;
}

/* Hide Streamlit top decoration bar */
[data-testid="stDecoration"] {
    display: none !important;
}

/* Streamlit header bar */
[data-testid="stHeader"] {
    background: rgba(236, 231, 209, 0.9) !important;
    backdrop-filter: blur(10px) !important;
}

/* Widget base containers */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] span,
[data-testid="stMarkdownContainer"] p {
    color: #3A2E1F !important;
    font-weight: 600 !important;
}

/* ─── Background with animation ─── */
.stApp {
    background: linear-gradient(-45deg, #ECE7D1, #E3DCBF, #DBCEA5, #ECE7D1, #F2EEE0) !important;
    background-size: 400% 400% !important;
    animation: bgShift 20s ease infinite !important;
}

@keyframes bgShift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(18px); }
    to { opacity: 1; transform: translateY(0); }
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes warmPulse {
    0%, 100% { box-shadow: 0 4px 14px rgba(138, 118, 80, 0.25); }
    50% { box-shadow: 0 4px 22px rgba(138, 118, 80, 0.45); }
}

.block-container { animation: fadeInUp 0.7s ease-out; }

/* ─── Headers ─── */
h1 {
    color: #3A2E1F !important;
    -webkit-text-fill-color: #3A2E1F !important;
    font-weight: 900 !important;
    font-size: 2.6rem !important;
    letter-spacing: -0.01em !important;
    animation: fadeInUp 0.5s ease-out !important;
}

h2 {
    color: var(--text-dark) !important;
    font-weight: 700 !important;
    font-size: 1.45rem !important;
    border-bottom: 2px solid rgba(138, 118, 80, 0.3);
    padding-bottom: 8px;
    animation: fadeInUp 0.6s ease-out;
}

h3 { color: #3A2E1F !important; font-weight: 800 !important; }
p, li, span, label { color: #3A2E1F !important; font-weight: 600 !important; }

/* ─── All Input Labels ─── */
[data-testid="stSelectbox"] label,
[data-testid="stNumberInput"] label,
[data-testid="stSlider"] label {
    color: #3A2E1F !important;
    font-weight: 700 !important;
    font-size: 0.92rem !important;
}

/* ─── Select Boxes ─── */
[data-testid="stSelectbox"] > div > div {
    background: #DBCEA5 !important;
    border: 1.5px solid #8A7650 !important;
    border-radius: 10px !important;
    color: #3A2E1F !important;
    font-weight: 600 !important;
    transition: all 0.3s ease !important;
}

[data-testid="stSelectbox"] > div > div:hover {
    border-color: #6B5D48 !important;
    box-shadow: 0 3px 12px rgba(138, 118, 80, 0.2) !important;
}

/* Dropdown selected text */
[data-testid="stSelectbox"] span {
    color: #3A2E1F !important;
    font-weight: 600 !important;
}

/* Dropdown menu list */
[data-testid="stSelectbox"] ul {
    background: #ECE7D1 !important;
    border: 1.5px solid #8A7650 !important;
    border-radius: 10px !important;
}

[data-testid="stSelectbox"] li {
    color: #3A2E1F !important;
    font-weight: 500 !important;
}

[data-testid="stSelectbox"] li:hover {
    background: #DBCEA5 !important;
}

/* ─── Number Inputs ─── */
[data-testid="stNumberInput"] input {
    background: #DBCEA5 !important;
    border: 1.5px solid #8A7650 !important;
    border-radius: 10px !important;
    color: #3A2E1F !important;
    font-weight: 600 !important;
    transition: all 0.3s ease !important;
}

[data-testid="stNumberInput"] input:focus {
    border-color: #6B5D48 !important;
    box-shadow: 0 3px 12px rgba(138, 118, 80, 0.25) !important;
}

/* Stepper +/- buttons */
[data-testid="stNumberInput"] button {
    background: #8A7650 !important;
    border: none !important;
    color: #ECE7D1 !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
}

[data-testid="stNumberInput"] button:hover {
    background: #6B5D48 !important;
}

/* ─── Slider ─── */
[data-testid="stSlider"] > div > div > div > div {
    background: linear-gradient(90deg, var(--bronze), var(--sage)) !important;
}

[data-testid="stSlider"] [role="slider"] {
    background: var(--bronze) !important;
    border: 3px solid var(--cream) !important;
    box-shadow: 0 2px 8px rgba(138, 118, 80, 0.35) !important;
    transition: all 0.2s ease !important;
}

[data-testid="stSlider"] [role="slider"]:hover {
    transform: scale(1.15) !important;
    box-shadow: 0 3px 14px rgba(138, 118, 80, 0.5) !important;
}

/* ─── Primary Button (Generate) ─── */
button[kind="primary"] {
    background: linear-gradient(135deg, var(--bronze), var(--sage)) !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 1.05rem !important;
    padding: 0.7rem 2rem !important;
    letter-spacing: 0.03em !important;
    color: var(--cream) !important;
    transition: all 0.3s ease !important;
    animation: warmPulse 3s infinite !important;
    text-transform: uppercase !important;
}

button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 28px rgba(138, 118, 80, 0.4) !important;
}

button[kind="primary"]:active { transform: translateY(0) !important; }

/* ─── Download Button ─── */
button[kind="secondary"], [data-testid="stDownloadButton"] button {
    background: rgba(255, 255, 255, 0.5) !important;
    border: 1px solid rgba(138, 118, 80, 0.3) !important;
    border-radius: 10px !important;
    color: var(--text-dark) !important;
    font-weight: 500 !important;
    transition: all 0.3s ease !important;
}

[data-testid="stDownloadButton"] button:hover {
    background: rgba(138, 118, 80, 0.1) !important;
    border-color: var(--bronze) !important;
    box-shadow: 0 3px 14px rgba(138, 118, 80, 0.18) !important;
    transform: translateY(-1px) !important;
}

/* ─── WhatsApp Link ─── */
[data-testid="stLinkButton"] a {
    background: rgba(142, 151, 125, 0.15) !important;
    border: 1px solid rgba(142, 151, 125, 0.4) !important;
    border-radius: 10px !important;
    color: #5C6B4A !important;
    font-weight: 500 !important;
    transition: all 0.3s ease !important;
    text-decoration: none !important;
}

[data-testid="stLinkButton"] a:hover {
    background: rgba(142, 151, 125, 0.28) !important;
    box-shadow: 0 3px 12px rgba(142, 151, 125, 0.22) !important;
    transform: translateY(-1px) !important;
}

/* ─── Success Alert ─── */
[data-testid="stAlert"] {
    background: rgba(142, 151, 125, 0.12) !important;
    border: 1px solid rgba(142, 151, 125, 0.3) !important;
    border-radius: 12px !important;
}

/* ─── Dividers ─── */
hr {
    border: none !important;
    height: 2px !important;
    background: linear-gradient(90deg, transparent, rgba(138, 118, 80, 0.3), rgba(142, 151, 125, 0.25), transparent) !important;
    margin: 1.5rem 0 !important;
}

[data-testid="stSpinner"] { color: var(--bronze) !important; }
.stMarkdown { animation: fadeIn 0.6s ease-out; }

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--cream); }
::-webkit-scrollbar-thumb { background: var(--tan); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--bronze); }

</style>
""", unsafe_allow_html=True)

# ─── Title ───
st.markdown("""
<div style="text-align: center; animation: fadeInUp 0.5s ease-out; margin-bottom: 0.5rem;">
    <h1 style="margin-bottom: 0.2rem;">AI Student Travel Planner</h1>
    <p style="
        font-size: 1.1rem;
        color: #8A7650 !important;
        font-weight: 300;
        letter-spacing: 0.02em;
        animation: fadeIn 0.8s ease-out;
    ">
        Plan your perfect student trip with AI-powered itineraries and destination visuals.
    </p>
</div>
""", unsafe_allow_html=True)

# ─── Trip Details ───
st.header("Trip Details")
col1, col2 = st.columns(2)

with col1:
    country = st.selectbox("Select Country", ALL_COUNTRIES, index=ALL_COUNTRIES.index("India"))
    cities_in_country = COUNTRY_CITIES.get(country, [])
    source = st.selectbox("Source City", cities_in_country, index=0)
    dest_options = [c for c in cities_in_country if c != source]
    destination = st.selectbox("Destination City", dest_options, index=min(1, len(dest_options)-1))
    duration = st.number_input("Trip Duration (Days)", min_value=1, max_value=30, value=3)

with col2:
    travel_style = st.selectbox("Travel Style", ["Backpacking","Flashpacking","Minimalist","Relaxed Chill"])
    transport = st.selectbox("Transport Preference", ["Train (Sleeper/General)","Bus / Volvo","Budget Flight","Hitchhiking / Local"])
    food = st.selectbox("Food Preference", ["Street Food & Local Joints","Strictly Vegetarian","Vegan / Healthy","Everything"])
    accommodation = st.selectbox("Accommodation Choice", ["Hostel","Dormitory / Dharamshala","Couchsurfing","Budget Hotel","Homestay"])

budget = st.slider("Total Budget (₹)", min_value=500, max_value=100000, value=5000, step=500)

generate_btn = st.button("Generate Itinerary", use_container_width=True, type="primary")


# ─── Hugging Face Image Generator (New Router API) ───
HF_MODELS = [
    "black-forest-labs/FLUX.1-schnell",
    "stabilityai/stable-diffusion-xl-base-1.0",
]

def hf_generate_image(prompt):
    """Generate an AI image using Hugging Face — fast timeout, first success wins."""
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    for model in HF_MODELS:
        try:
            url = f"https://router.huggingface.co/hf-inference/models/{model}"
            resp = requests.post(url, headers=headers, json={"inputs": prompt}, timeout=8)
            if resp.status_code == 200:
                return Image.open(io.BytesIO(resp.content))
        except Exception:
            continue
    return None


# ─── Wikipedia Image Fetcher (Fallback) ───
WIKI_HEADERS = {"User-Agent": "AIStudentTravelPlanner/1.0 (student-project)"}

def fetch_wiki_image(search_term):
    """Fetch the main image from the most relevant Wikipedia article."""
    try:
        search_url = (
            "https://en.wikipedia.org/w/api.php?action=query&list=search"
            f"&srsearch={urllib.parse.quote(search_term)}&utf8=&format=json&srlimit=1"
        )
        res = requests.get(search_url, headers=WIKI_HEADERS, timeout=6).json()
        if not res.get("query", {}).get("search"):
            return None
        title = res["query"]["search"][0]["title"]
        img_url = (
            "https://en.wikipedia.org/w/api.php?action=query"
            f"&titles={urllib.parse.quote(title)}&prop=pageimages&pithumbsize=1024&format=json"
        )
        res2 = requests.get(img_url, headers=WIKI_HEADERS, timeout=6).json()
        for page in res2.get("query", {}).get("pages", {}).values():
            if "thumbnail" in page:
                img_data = requests.get(page["thumbnail"]["source"], headers=WIKI_HEADERS, timeout=6).content
                return Image.open(io.BytesIO(img_data))
    except Exception:
        pass
    return None


# ─── Get 5 Specific Famous Places from Groq ───
def get_famous_places(destination, country):
    """Ask Groq to return exactly 5 specific famous tourist attractions."""
    try:
        client = Groq(api_key=GROQ_API_KEY)
        chat = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a travel expert. Respond with ONLY a numbered list of exactly 5 items, nothing else. No descriptions, no extra text."},
                {"role": "user", "content": f"List exactly 5 most famous and visually iconic tourist attractions or landmarks in {destination}, {country}. Only real, well-known places."},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=200,
        )
        response = chat.choices[0].message.content.strip()
        places = []
        for line in response.split("\n"):
            line = line.strip()
            if not line:
                continue
            cleaned = re.sub(r"^\d+[\.\)\:\-]\s*", "", line).strip()
            if cleaned and len(cleaned) > 2:
                places.append(cleaned)
        return places[:5]
    except Exception:
        return [
            f"{destination} main landmark",
            f"{destination} temple",
            f"{destination} fort",
            f"{destination} palace",
            f"{destination} monument",
        ]


# ─── Fetch a single place image (HF first, then Wikipedia) ───
def fetch_place_image(place_name, destination, country):
    """Try HF AI first, then Wikipedia. Returns (image, place_name)."""
    img = None
    # Tier 1: Hugging Face AI
    try:
        prompt = f"Beautiful photograph of {place_name} in {destination}, {country}, stunning architecture, clear sky, professional travel photography, 4k"
        img = hf_generate_image(prompt)
    except Exception:
        pass
    # Tier 2: Wikipedia
    if img is None:
        img = fetch_wiki_image(f"{place_name} {destination}")
        if img is None:
            img = fetch_wiki_image(place_name)
    return (img, place_name)


# ─── Generate All 5 Images IN PARALLEL (Fast!) ───
def generate_all_images(destination, country):
    """
    1. Get 5 famous places from Groq (~1s).
    2. Fetch all 5 images IN PARALLEL (~8s instead of ~40s).
    """
    places = get_famous_places(destination, country)

    results = [None] * len(places)
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_idx = {
            executor.submit(fetch_place_image, place, destination, country): i
            for i, place in enumerate(places)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception:
                results[idx] = (None, places[idx])

    return results


# ─── Groq Itinerary Generator ───
def generate_itinerary(source, destination, country, duration, budget, travel_style, transport, food, accommodation):
    client = Groq(api_key=GROQ_API_KEY)
    prompt = f"""Act as a professional and highly organized AI travel planner tailored for college students on a budget.
Create a highly detailed, realistic, and budget-friendly day-wise travel itinerary:

- Country: {country}
- Source city: {source}
- Destination city: {destination}
- Trip duration: {duration} days
- Total budget: ₹{budget}
- Travel style: {travel_style}
- Transport preference: {transport}
- Food preference: {food}
- Accommodation choice: {accommodation}

Include:
1. Executive summary of the trip
2. Structured day-wise itinerary
3. Detailed budget breakdown (transport, stay, food, activities, misc) strictly within ₹{budget}
4. Cost-effective stay recommendations
5. Local budget-friendly food options
6. Low-cost or free attractions in {destination}
7. Essential safety and cost-saving tips

Use clean professional Markdown with clear headings and bullet points. Tone should be professional, practical, and highly informative. Do not use any emojis in your response."""

    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are an expert professional travel planner. Give detailed, realistic, and highly structured travel itineraries."},
            {"role": "user", "content": prompt},
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.5,
        max_tokens=4096,
    )
    return chat_completion.choices[0].message.content


# ─── Image → Base64 helper ───
def pil_to_b64(pil_img):
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# ─── Beautiful HTML/PDF Generator ───
def sanitize_for_pdf(text):
    """Replace Unicode chars with ASCII equivalents for fpdf2 compatibility."""
    replacements = {
        '\u20b9': 'Rs.',    # ₹
        '\u2192': '->',     # →
        '\u2190': '<-',     # ←
        '\u2194': '<->',    # ↔
        '\u2022': '-',      # •
        '\u2013': '-',      # –
        '\u2014': '--',     # —
        '\u2018': "'",      # '
        '\u2019': "'",      # '
        '\u201c': '"',      # "
        '\u201d': '"',      # "
        '\u2026': '...',    # …
        '\u2713': '[OK]',   # ✓
        '\u2714': '[OK]',   # ✔
        '\u2716': '[X]',    # ✖
        '\u2605': '*',      # ★
        '\u2606': '*',      # ☆
        '\u00b0': 'deg',    # °
        '\xa0': ' ',        # non-breaking space
    }
    for uchar, ascii_rep in replacements.items():
        text = text.replace(uchar, ascii_rep)
    # Strip any remaining non-latin1 characters
    return text.encode('latin-1', errors='replace').decode('latin-1')


def create_pdf(itinerary_text, source, destination, country, images):
    """Generate a styled PDF using fpdf2 (pure Python, no C deps)."""
    # Sanitize all text inputs
    itinerary_text = sanitize_for_pdf(itinerary_text)
    source = sanitize_for_pdf(source)
    destination = sanitize_for_pdf(destination)
    country = sanitize_for_pdf(country)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ── Title ──
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(58, 46, 31)  # #3A2E1F
    pdf.cell(0, 12, "AI Student Travel Itinerary", ln=True, align="C")
    pdf.ln(2)

    # ── Route info ──
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(107, 93, 72)  # #6B5D48
    pdf.cell(0, 8, f"Route: {source}  -->  {destination}, {country}", ln=True, align="C")
    pdf.ln(4)
    pdf.set_draw_color(138, 118, 80)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # ── Images ──
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(58, 46, 31)
    pdf.cell(0, 8, "Trip Gallery", ln=True)
    pdf.ln(2)

    x_start = 15
    img_w = 85
    col = 0
    for img, label in images:
        if img:
            try:
                tmp = io.BytesIO()
                img.save(tmp, format="PNG")
                tmp.seek(0)
                x = x_start + col * (img_w + 10)
                y = pdf.get_y()
                if y + 65 > 280:
                    pdf.add_page()
                    y = pdf.get_y()
                pdf.image(tmp, x=x, y=y, w=img_w)
                pdf.set_xy(x, y + 55)
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(107, 93, 72)
                pdf.cell(img_w, 5, sanitize_for_pdf(label), align="C")
                col += 1
                if col >= 2:
                    col = 0
                    pdf.ln(62)
            except Exception:
                pass

    if col == 1:
        pdf.ln(62)
    pdf.ln(6)
    pdf.set_draw_color(138, 118, 80)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # ── Itinerary Text ──
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(51, 51, 51)
    left_margin = pdf.l_margin
    for line in itinerary_text.split("\n"):
        clean = line.strip()
        if not clean:
            pdf.ln(3)
            continue
        try:
            # Always reset X to left margin
            pdf.set_x(left_margin)
            # Headings
            if clean.startswith("### "):
                pdf.set_font("Helvetica", "B", 11)
                pdf.set_text_color(107, 93, 72)
                pdf.multi_cell(0, 6, clean.replace("### ", ""))
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(51, 51, 51)
            elif clean.startswith("## "):
                pdf.set_font("Helvetica", "B", 13)
                pdf.set_text_color(138, 118, 80)
                pdf.multi_cell(0, 7, clean.replace("## ", ""))
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(51, 51, 51)
            elif clean.startswith("# "):
                pdf.set_font("Helvetica", "B", 16)
                pdf.set_text_color(58, 46, 31)
                pdf.multi_cell(0, 8, clean.replace("# ", ""))
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(51, 51, 51)
            elif clean.startswith("- ") or clean.startswith("* "):
                bullet_text = "  - " + clean[2:].replace("**", "")
                pdf.multi_cell(0, 5, bullet_text)
            elif clean.startswith("|"):
                # Table row
                cells = [c.strip() for c in clean.split("|")[1:-1]]
                if cells and all(c.replace("-", "").strip() == "" for c in cells):
                    continue  # skip separator row
                col_w = min(190 / max(len(cells), 1), 95)
                pdf.set_font("Helvetica", "", 9)
                for cell in cells:
                    cell_text = cell.replace("**", "")[:40]  # truncate long cells
                    pdf.cell(col_w, 6, cell_text, border=1)
                pdf.ln()
                pdf.set_font("Helvetica", "", 10)
            else:
                clean = clean.replace("**", "")
                pdf.multi_cell(0, 5, clean)
        except Exception:
            # If any line fails, just skip it
            pdf.ln(5)
            continue

    # ── Footer ──
    pdf.ln(10)
    pdf.set_x(left_margin)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(140, 140, 140)
    pdf.cell(0, 5, "Generated by AI Student Travel Planner", ln=True, align="C")

    return pdf.output()


# ─── Swiper.js Carousel Builder ───
def build_carousel(images, destination, country):
    slides_html = ""
    for img, label in images:
        if img:
            b64 = pil_to_b64(img)
            src = f"data:image/png;base64,{b64}"
        else:
            src = "https://placehold.co/900x500/1a1a2e/ffffff?text=Image+Unavailable"
        slides_html += f"""
        <div class="swiper-slide">
            <img src="{src}" />
            <div class="caption">{label}</div>
        </div>"""

    html = f"""
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.css" />
    <style>
      .swiper {{
        width: 100%; height: 480px;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
      }}
      .swiper-slide {{
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #f8f9fa;
      }}
      .swiper-slide img {{
        width: 100%; height: 100%;
        object-fit: contain;
        display: block;
        background: #0a0a0a;
      }}
      .caption {{
        position: absolute;
        bottom: 0; left: 0; right: 0;
        background: linear-gradient(transparent, rgba(0,0,0,0.8));
        color: #fff;
        font-size: 1.1rem;
        font-weight: 500;
        padding: 18px 20px 14px;
        font-family: 'Inter', sans-serif;
        letter-spacing: 0.01em;
      }}
      .swiper-button-next, .swiper-button-prev {{
        color: #fff;
        background: rgba(0,0,0,0.3);
        width: 40px; height: 40px;
        border-radius: 50%;
        backdrop-filter: blur(4px);
      }}
      .swiper-button-next::after, .swiper-button-prev::after {{
        font-size: 1rem; font-weight: 700;
      }}
      .swiper-pagination-bullet {{ background: #fff; opacity: 0.6; }}
      .swiper-pagination-bullet-active {{ opacity: 1; background: #2c3e50; }}
      h3.gallery-title {{
        font-family: 'Inter', sans-serif;
        color: #2c3e50;
        margin-bottom: 12px;
        font-size: 1.3rem;
        font-weight: 600;
        letter-spacing: 0.02em;
      }}
    </style>
    <h3 class="gallery-title">{destination}, {country} — Photo Gallery</h3>
    <div class="swiper mySwiper">
      <div class="swiper-wrapper">
        {slides_html}
      </div>
      <div class="swiper-pagination"></div>
      <div class="swiper-button-prev"></div>
      <div class="swiper-button-next"></div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.js"></script>
    <script>
      const swiper = new Swiper('.mySwiper', {{
        loop: true,
        autoplay: {{ delay: 3500, disableOnInteraction: false }},
        effect: 'slide',
        speed: 700,
        pagination: {{ el: '.swiper-pagination', clickable: true }},
        navigation: {{ nextEl: '.swiper-button-next', prevEl: '.swiper-button-prev' }},
      }});
    </script>
    """
    return html


# ─── Main Logic ───
if generate_btn:
    st.divider()
    with st.spinner(f"Generating photos of {destination} & crafting your itinerary in parallel... Please wait."):
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                img_future = executor.submit(generate_all_images, destination, country)
                txt_future = executor.submit(
                    generate_itinerary,
                    source, destination, country, duration, budget,
                    travel_style, transport, food, accommodation
                )
                images    = img_future.result()
                itinerary = txt_future.result()

            # Save to session state so it persists across reruns
            st.session_state["itinerary"] = itinerary
            st.session_state["images"] = images
            st.session_state["trip_source"] = source
            st.session_state["trip_destination"] = destination
            st.session_state["trip_country"] = country

        except Exception as e:
            st.error(f"An error occurred: {e}")

# ─── Display Results (from session state, persists across button clicks) ───
if "itinerary" in st.session_state:
    itinerary = st.session_state["itinerary"]
    images = st.session_state["images"]
    trip_src = st.session_state["trip_source"]
    trip_dest = st.session_state["trip_destination"]
    trip_country = st.session_state["trip_country"]

    st.divider()

    # ── Action Buttons ──
    st.success("Your itinerary has been successfully generated.")
    btn_col1, btn_col2 = st.columns(2)

    with btn_col1:
        pdf_bytes = create_pdf(itinerary, trip_src, trip_dest, trip_country, images)
        st.download_button(
            label="Download as PDF",
            data=pdf_bytes,
            file_name=f"{trip_src}_to_{trip_dest}_itinerary.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    with btn_col2:
        short_text = (
            f"My Student Travel Itinerary\n"
            f"{trip_src} -> {trip_dest}, {trip_country}\n\n"
            f"{itinerary[:800]}...\n\n"
            f"Generated by AI Student Travel Planner"
        )
        wa_url = f"https://wa.me/?text={urllib.parse.quote(short_text)}"
        st.link_button(
            label="Share on WhatsApp",
            url=wa_url,
            use_container_width=True,
        )

    st.divider()

    # ── Swiper Carousel ──
    carousel_html = build_carousel(images, trip_dest, trip_country)
    st.components.v1.html(carousel_html, height=540, scrolling=False)

    st.divider()

    # ── Itinerary ──
    st.subheader("Your Custom Itinerary")
    st.markdown(itinerary)

