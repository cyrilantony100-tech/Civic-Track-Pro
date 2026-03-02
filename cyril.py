import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Text, LargeBinary
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from passlib.context import CryptContext
from datetime import datetime

# ==========================================
# 1. DATABASE SETUP
# ==========================================
DATABASE_URL = "sqlite:///civictrack_pro.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ✅ STABLE PASSWORD HASHING (NO BCRYPT)
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto"
)

DEPARTMENTS = {
    "Infrastructure": "Public Works Dept.",
    "Sanitation": "Municipal Sanitation Dept.",
    "Water Supply": "Jal Board",
    "Electricity": "Power Distribution Dept.",
    "Health": "Health & Sanitation Dept.",
    "Education": "Municipal Education Dept.",
    "Transport": "Transport Authority",
    "Other": "General Administration"
}

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)
    role = Column(String, default="citizen")
    department = Column(String, nullable=True)
    issues = relationship("Issue", back_populates="owner")

class Issue(Base):
    __tablename__ = "issues"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(Text)
    category = Column(String)
    location = Column(String)
    ward = Column(String, nullable=True)
    status = Column(String, default="Pending")
    upvotes = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    assigned_dept = Column(String, nullable=True)
    image_data = Column(LargeBinary, nullable=True)
    image_name = Column(String, nullable=True)
    priority = Column(String, default="Normal")
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="issues")

Base.metadata.create_all(bind=engine)

# ==========================================
# 2. AUTH LOGIC
# ==========================================
def safe_hash(password):
    if not password:
        return ""
    return pwd_context.hash(password)

def verify_password(password, hashed):
    if not password or not hashed:
        return False
    return pwd_context.verify(password, hashed)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_user(username, password, role="citizen", department=None):
    db = next(get_db())
    if db.query(User).filter(User.username == username).first():
        return False
    user = User(
        username=username,
        password=safe_hash(password),
        role=role,
        department=department
    )
    db.add(user)
    db.commit()
    return True

def bootstrap_system():
    db = next(get_db())
    if not db.query(User).filter(User.role == "admin").first():
        create_user("admin", "admin123", role="admin", department="General Administration")

# ==========================================
# 3. ISSUE LOGIC
# ==========================================
def create_issue(title, desc, category, location, ward, user_id):
    db = next(get_db())
    dept = DEPARTMENTS.get(category, "General Administration")
    issue = Issue(
        title=title,
        description=desc,
        category=category,
        location=location,
        ward=ward,
        owner_id=user_id,
        assigned_dept=dept
    )
    db.add(issue)
    db.commit()

def get_all_issues():
    db = next(get_db())
    return db.query(Issue).order_by(Issue.created_at.desc()).all()

def upvote_issue(issue_id):
    db = next(get_db())
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if issue:
        issue.upvotes += 1
        db.commit()

def update_status(issue_id, status):
    db = next(get_db())
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if issue:
        issue.status = status
        issue.updated_at = datetime.utcnow()
        db.commit()

# ==========================================
# 4. STREAMLIT UI
# ==========================================
bootstrap_system()

st.set_page_config(page_title="CivicTrack Pro", page_icon="🏛️", layout="wide")

if "user_id" not in st.session_state:
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.role = None

st.title("🏛️ CivicTrack Pro Portal")

# ================= LOGIN / REGISTER =================
if not st.session_state.user_id:

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            db = next(get_db())
            user = db.query(User).filter(User.username == username).first()
            if user and verify_password(password, user.password):
                st.session_state.user_id = user.id
                st.session_state.username = user.username
                st.session_state.role = user.role
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab2:
        new_user = st.text_input("New Username")
        new_pass = st.text_input("New Password", type="password")
        if st.button("Create Account"):
            if create_user(new_user, new_pass):
                st.success("Account created! Please login.")
            else:
                st.error("Username already exists.")

# ================= MAIN APP =================
else:

    st.sidebar.title(f"👋 {st.session_state.username}")
    st.sidebar.write(f"Role: {st.session_state.role}")

    if st.sidebar.button("Logout"):
        st.session_state.user_id = None
        st.rerun()

    menu = st.sidebar.radio("Menu", ["Feed", "Report Issue", "Admin Panel"])

    if menu == "Feed":
        st.header("Community Issues")
        issues = get_all_issues()
        for issue in issues:
            st.subheader(issue.title)
            st.write(f"📍 {issue.location}")
            st.write(f"Status: {issue.status}")
            st.write(issue.description)
            if st.button(f"👍 Upvote ({issue.upvotes})", key=f"up_{issue.id}"):
                upvote_issue(issue.id)
                st.rerun()
            st.divider()

    elif menu == "Report Issue":
        st.header("Submit New Issue")
        with st.form("issue_form"):
            title = st.text_input("Title")
            category = st.selectbox("Category", list(DEPARTMENTS.keys()))
            location = st.text_input("Location")
            description = st.text_area("Description")
            submit = st.form_submit_button("Submit")
            if submit:
                create_issue(
                    title,
                    description,
                    category,
                    location,
                    "Ward 1",
                    st.session_state.user_id
                )
                st.success("Issue submitted successfully!")

    elif menu == "Admin Panel":
        if st.session_state.role == "admin":
            st.header("Admin Control Panel")
            issues = get_all_issues()
            for issue in issues:
                with st.expander(f"{issue.title} (#{issue.id})"):
                    new_status = st.selectbox(
                        "Update Status",
                        ["Pending", "In Progress", "Resolved"],
                        key=f"status_{issue.id}"
                    )
                    if st.button("Update", key=f"btn_{issue.id}"):
                        update_status(issue.id, new_status)
                        st.success("Updated!")
                        st.rerun()
        else:
            st.warning("Admins only.")