
# 📌 AI Voice-Based Interview System — README

## 🟡 Live Demo
👉 https://eightfoldai-chat.netlify.app/

## 👤 Author
**Gugan J** — B.Tech Artificial Intelligence & Data Science  
**Rathinam Technical Campus, Coimbatore**  
**Expertise:** Machine Learning • IoT • Full-Stack Development • Cloud Deployment

---

# 🚀 Project Overview
A fully automated **AI-powered voice + text interview system** that adapts to:

- **6 major domains** (Software Engineering, Data Science, Product Management, Design, Marketing, Sales)
- **Any custom role**
- **10–30 minute interview duration**
- **Male / Female AI voice**
- **Adaptive question flow**
- **Real-time Speech-to-Text & AI Voice Output**

Works flawlessly end-to-end across Netlify + Render + Firebase.

---

# 🧩 Features
- 🎤 Real-time STT (Browser API)
- 🔊 AI TTS (11Labs)
- 🤖 AI responses (OpenRouter)
- 🔐 Firebase Auth + Google OAuth
- 🌐 Netlify Frontend
- 🖥️ Render Flask Backend
- ⚙ Domain, role, duration, and voice selection

---

# 📦 Tech Stack (Text Boxes)

```
+----------------------+
|      FRONTEND        |
+----------------------+
| HTML                 |
| CSS                  |
| JavaScript           |
| Netlify Hosting      |
+----------------------+

+----------------------+
|       BACKEND        |
+----------------------+
| Python               |
| Flask (REST API)     |
| Render Hosting       |
+----------------------+

+----------------------+
|     AI SERVICES      |
+----------------------+
| OpenRouter API       |
| Rotational Keys      |
| Domain/Role Logic    |
+----------------------+

+----------------------+
|   SPEECH ENGINE      |
+----------------------+
| Browser STT API      |
| 11Labs TTS           |
+----------------------+

+----------------------+
|   AUTHENTICATION     |
+----------------------+
| Firebase Auth        |
| Google OAuth         |
+----------------------+
```

---

# 🗂 System Architecture Diagram (Text Flow)

```
[ User ]
    |
    v
[ Browser STT ]
    | Speech → Text
    v
[ Frontend (Netlify) ]
    | Sends response
    v
[ Backend (Flask - Render) ]
    | Processes request
    v
[ OpenRouter API ]
    | AI reply
    v
[ Backend ]
    | Sends text
    v
[ 11Labs TTS ]
    | Text → Voice
    v
[ Frontend ]
    | Plays audio + shows text
    v
[ User continues conversation ]

-------------- AUTH FLOW --------------

[ Login Request ]
    |
    v
[ Firebase Auth ]
    | Email/Password + Google OAuth
    v
[ Access Granted ]
```

---

# 📎 Notes
- Needs `.env` file with API keys  
- Firebase config must be updated for production  
- Works fully on free-tier hosting
