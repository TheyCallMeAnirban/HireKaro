# HireKaro 🚀

**HireKaro** is a high-performance, AI-powered talent scouting application designed for modern recruiters. It automates the extraction, matching, and evaluation of technical candidates by securely pairing deterministic vector-embedding scoring with targeted Large Language Model (LLM) summaries.

![HireKaro Pipeline](https://images.unsplash.com/photo-1551434678-e076c223a692?q=80&w=2850&auto=format&fit=crop)

## ✨ Core Features

- **Automated Bias Detection:** Flags exclusionary language in Job Descriptions instantly before processing candidates.
- **Lightning-Fast Vector Matching:** Converts resumes and job descriptions into vector embeddings for 0-latency, deterministic cosine-similarity matching.
- **Deep Intelligence Briefs:** Uses Google's Gemini 2.0 Flash to generate actionable summaries (strengths, gaps, and recommendations) exclusively for the top 8 ranked candidates.
- **Concurrency & Cost Optimized:** Re-architected in v3.0 to drastically reduce LLM API calls from >60 per request down to under 10 using `asyncio.Semaphore` and `ThreadPoolExecutor`.
- **Hybrid Data Layer:** Uses **MongoDB** for secure operative (recruiter) authentication and a **SQLite WAL** database for ultra-fast, concurrent historical pipeline storage.
- **Intelligence Guild Dashboard:** A premium, dark-mode React 19 interface built with Vite, Tailwind CSS v4, and `framer-motion` for a futuristic operative experience.

## 🛠️ System Architecture

### Backend (Python / FastAPI)
- **Framework:** FastAPI for high-performance async REST endpoints.
- **LLM Integration:** `google-genai` for parsing, bias detection, and intelligence briefs.
- **Databases:** MongoDB (`pymongo`) for Authentication & User profiles; SQLite3 (WAL Mode) for persistent history logs.
- **Resiliency:** Rate limiting with `slowapi` and built-in circuit-breakers for LLM fallbacks.

### Frontend (React / TypeScript)
- **Framework:** React 19 powered by Vite for rapid HMR.
- **Styling:** Tailwind CSS v4 + Lucide React for sleek, scalable UI components.
- **Animations:** Framer Motion for liquid-smooth transitions.
- **Security:** JWT-based session management (`localStorage`) wrapped behind an encrypted login wall.

## ⚙️ Getting Started

### Prerequisites
- Node.js (v18+)
- Python 3.10+
- A running MongoDB instance (Local on port 27017, or MongoDB Atlas)

### 1. Backend Setup

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file inside the `backend/` directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
MONGO_URI=mongodb://localhost:27017/
JWT_SECRET=your_super_secret_jwt_key
```

Run the backend server:
```bash
uvicorn main:app --reload
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Navigate to `http://localhost:3000`. You will be greeted by the HireKaro Login Wall. Register a new operative account to gain clearance and access the pipeline dashboard.

## 🤝 Contributing
Contributions, issues, and feature requests are welcome. Feel free to check the [issues page](#) if you want to contribute.

## 📝 License
This project is licensed under the MIT License.
