
import streamlit as st
import requests
import os
from io import BytesIO
from PIL import Image

API_URL = os.getenv("API_URL", "http://localhost:8000")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

st.set_page_config(page_title="Civic Reporter", layout="wide")

def geocode_address(addr):
    if not addr or not GOOGLE_API_KEY:
        return None, None
    import requests
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    r = requests.get(url, params={"address": addr, "key": GOOGLE_API_KEY})
    data = r.json()
    if data.get("results"):
        loc = data["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    return None, None

def upload_complaint(title, description, address, email, photo_bytes, latitude=None, longitude=None):
    files = {}
    data = {
        "title": title,
        "description": description or "",
        "address": address or "",
        "reporter_email": email or "",
    }
    if latitude:
        data["latitude"] = str(latitude)
    if longitude:
        data["longitude"] = str(longitude)

    if photo_bytes:
        files["photo"] = ("photo.jpg", photo_bytes, "image/jpeg")
    resp = requests.post(f"{API_URL}/complaints/", data=data, files=files)
    return resp

def show_map_for_items(items):
    markers = []
    for it in items:
        if it.get("latitude") and it.get("longitude"):
            markers.append(f"{it['latitude']},{it['longitude']}")
    if not markers:
        st.info("No geo-tagged complaints to show.")
        return
    center = markers[0]
    map_url = f"https://maps.google.com/maps?q={center}&z=15&output=embed"
    st.components.v1.iframe(map_url, height=450, scrolling=False)

st.sidebar.title("Civic Reporter")
page = st.sidebar.radio("Go to", ["Report Issue", "My Complaint Status", "Public Dashboard", "Admin"])

if page == "Report Issue":
    st.title("Report a civic issue")
    with st.form("report_form"):
        title = st.text_input("Title (e.g., Pothole near 5th street)")
        description = st.text_area("Description")
        address = st.text_input("Address or landmark")
        col1, col2 = st.columns([1,1])
        with col1:
            photo = st.file_uploader("Photo (optional)", type=["png","jpg","jpeg"])
        with col2:
            email = st.text_input("Your email (optional, for updates)")
        submitted = st.form_submit_button("Submit")
        if submitted:
            lat, lng = None, None
            if address:
                lat, lng = geocode_address(address)
            photo_bytes = None
            if photo:
                img = Image.open(photo)
                buf = BytesIO()
                img.save(buf, format="JPEG")
                buf.seek(0)
                photo_bytes = buf.read()
            resp = upload_complaint(title, description, address, email, photo_bytes, lat, lng)
            if resp.status_code in [200,201]:
                data = resp.json()
                st.success(f"Complaint submitted! Your complaint ID is {data['id']}")
                st.info("Save the ID to check status later.")
            else:
                st.error(f"Failed to submit: {resp.text}")

elif page == "My Complaint Status":
    st.title("Check status (Chatbot)")
    cid = st.text_input("Complaint ID")
    if st.button("Check"):
        if not cid.isdigit():
            st.error("Please enter a numeric complaint ID")
        else:
            r = requests.get(f"{API_URL}/complaints/{int(cid)}")
            if r.status_code == 200:
                obj = r.json()
                st.write("**Title:**", obj["title"])
                st.write("**Status:**", obj["status"])
                st.write("**Description:**", obj["description"])
                if obj.get("photo_path"):
                    filename = obj["photo_path"].split("/")[-1]
                    img_url = f"{API_URL}/uploads/{filename}"
                    st.image(img_url, width=400)
            else:
                st.error("Complaint not found")

elif page == "Public Dashboard":
    st.title("Public Dashboard — Resolved Issues")
    r = requests.get(f"{API_URL}/complaints/", params={"status":"Resolved"})
    if r.status_code == 200:
        items = r.json()
        st.write(f"Total resolved: {len(items)}")
        for it in items:
            st.markdown(f"**#{it['id']} — {it['title']}** — {it['address'] or 'No address'}")
            if it.get("photo_path"):
                fname = it["photo_path"].split("/")[-1]
                st.image(f"{API_URL}/uploads/{fname}", width=300)
        show_map_for_items(items)
    else:
        st.error("Failed to load public dashboard")

elif page == "Admin":
    st.title("Admin / Authority Dashboard")
    pw = st.text_input("Enter admin password", type="password")
    if pw != ADMIN_PASSWORD:
        st.warning("Provide admin password to continue (set as environment variable ADMIN_PASSWORD).")
        st.stop()
    st.success("Admin authenticated")
    q_status = st.selectbox("Filter by status", ["", "Pending", "In Progress", "Resolved"])
    r = requests.get(f"{API_URL}/complaints/", params={"status": q_status or None})
    if r.status_code == 200:
        items = r.json()
        for it in items:
            st.markdown(f"**#{it['id']} — {it['title']}** [{it['status']}]")
            st.write(it["description"])
            cols = st.columns([1,2,1])
            if it.get("photo_path"):
                fname = it["photo_path"].split("/")[-1]
                cols[0].image(f"{API_URL}/uploads/{fname}", width=150)
            new_status = cols[1].selectbox("Change status", ["Pending", "In Progress", "Resolved"], index=["Pending","In Progress","Resolved"].index(it["status"]), key=f"st_{it['id']}")
            note = cols[1].text_input("Admin note", key=f"note_{it['id']}")
            if cols[2].button("Update", key=f"update_{it['id']}"):
                payload = {"status": new_status, "admin_note": note}
                r2 = requests.patch(f"{API_URL}/complaints/{it['id']}", json=payload)
                if r2.status_code == 200:
                    st.success("Updated")
                else:
                    st.error("Failed to update")
    else:
        st.error("Failed to fetch complaints")
