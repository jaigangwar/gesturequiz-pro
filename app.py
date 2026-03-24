"""
GestureQuiz Pro - Flask Backend
================================
Run: python app.py
API Base: http://localhost:5000/api

New capabilities:
- Groq-powered AI coaching endpoints
- Live analytics dashboard data
- Classroom room creation/join/leaderboard
- Detailed session logging for frontend-only quizzes
"""

from collections import Counter
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import json
import os
import random
import sqlite3
import string
import time
import urllib.error
import urllib.request
import uuid

app = Flask(__name__)
CORS(app)

DB = "gesturequiz.db"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


QUESTION_BANK = {
    "pandas": {
        "name": "Python - Pandas",
        "emoji": "P",
        "questions": [
            {"q": "Which method reads a CSV file in Pandas?", "options": ["pd.read_file()", "pd.load_csv()", "pd.read_csv()", "pd.import_csv()"], "answer": "C", "topic": "I/O"},
            {"q": "How to select column 'age' from DataFrame df?", "options": ["df.get('age')", "df['age']", "df.select('age')", "df->age"], "answer": "B", "topic": "DataFrame"},
            {"q": "Which method drops rows with missing values?", "options": ["df.remove_null()", "df.clear_na()", "df.drop()", "df.dropna()"], "answer": "D", "topic": "Cleaning"},
            {"q": "What does df.shape return?", "options": ["Column names", "(rows,cols) tuple", "Data types", "Index values"], "answer": "B", "topic": "DataFrame"},
            {"q": "Which function merges DataFrames like SQL JOIN?", "options": ["pd.concat()", "pd.append()", "pd.merge()", "pd.join_tables()"], "answer": "C", "topic": "Merging"},
            {"q": "How to get descriptive statistics?", "options": ["df.info()", "df.stats()", "df.summary()", "df.describe()"], "answer": "D", "topic": "Stats"},
            {"q": "Which method groups data by column?", "options": ["df.group()", "df.groupby()", "df.cluster()", "df.partition()"], "answer": "B", "topic": "GroupBy"},
            {"q": "How to rename column 'old' to 'new'?", "options": ["df.columns['old']='new'", "df.rename_col()", "df.rename(columns={'old':'new'})", "df.update_col()"], "answer": "C", "topic": "Columns"},
            {"q": "Default index type in Pandas DataFrame?", "options": ["String labels", "Integer RangeIndex", "Date index", "UUID index"], "answer": "B", "topic": "Index"},
            {"q": "Which method fills NaN values with 0?", "options": ["df.fill(0)", "df.replace_na(0)", "df.fillna(0)", "df.set_null(0)"], "answer": "C", "topic": "Cleaning"},
        ],
    },
    "aiml": {
        "name": "AI & ML",
        "emoji": "AI",
        "questions": [
            {"q": "What does ML stand for?", "options": ["Machine Logic", "Machine Learning", "Model Learning", "Meta Learning"], "answer": "B", "topic": "Basics"},
            {"q": "Which is a supervised learning algorithm?", "options": ["K-Means", "DBSCAN", "Linear Regression", "PCA"], "answer": "C", "topic": "Algorithms"},
            {"q": "What is overfitting?", "options": ["Model too simple", "Model too complex for training", "Model not trained", "Data missing"], "answer": "B", "topic": "Concepts"},
            {"q": "Which activation function outputs 0 or 1?", "options": ["ReLU", "Sigmoid", "Tanh", "Softmax"], "answer": "B", "topic": "Neural Nets"},
            {"q": "What does CNN stand for?", "options": ["Central Neural Network", "Convolutional Neural Network", "Connected Node Network", "Cyclic Neural Net"], "answer": "B", "topic": "Deep Learning"},
            {"q": "Which library is used for ML in Python?", "options": ["NumPy", "Matplotlib", "Scikit-learn", "Requests"], "answer": "C", "topic": "Libraries"},
            {"q": "What is the purpose of a loss function?", "options": ["Activate neurons", "Measure prediction error", "Reduce data", "Store weights"], "answer": "B", "topic": "Training"},
            {"q": "Which is an unsupervised algorithm?", "options": ["Decision Tree", "Linear Regression", "K-Means Clustering", "SVM"], "answer": "C", "topic": "Algorithms"},
            {"q": "What does NLP stand for?", "options": ["Natural Logic Processing", "Neural Language Program", "Natural Language Processing", "Node Learning Protocol"], "answer": "C", "topic": "NLP"},
            {"q": "Backpropagation is used to?", "options": ["Feed data forward", "Update weights", "Store data", "Normalize inputs"], "answer": "B", "topic": "Training"},
        ],
    },
    "sqldsa": {
        "name": "SQL & DSA",
        "emoji": "SQL",
        "questions": [
            {"q": "Which SQL command retrieves data?", "options": ["GET", "FETCH", "SELECT", "RETRIEVE"], "answer": "C", "topic": "SQL"},
            {"q": "Which data structure uses LIFO?", "options": ["Queue", "Stack", "Linked List", "Tree"], "answer": "B", "topic": "DSA"},
            {"q": "Time complexity of linear search?", "options": ["O(log n)", "O(n^2)", "O(1)", "O(n)"], "answer": "D", "topic": "Algorithms"},
            {"q": "Which clause filters groups?", "options": ["WHERE", "FILTER", "HAVING", "CONDITION"], "answer": "C", "topic": "SQL"},
            {"q": "Height of balanced BST with 7 nodes?", "options": ["7", "4", "3", "2"], "answer": "C", "topic": "Trees"},
            {"q": "Which JOIN returns all rows from both tables?", "options": ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL OUTER JOIN"], "answer": "D", "topic": "SQL"},
            {"q": "Which sort has O(n log n) worst case?", "options": ["Bubble Sort", "Quick Sort", "Merge Sort", "Insertion Sort"], "answer": "C", "topic": "Sorting"},
            {"q": "What does PRIMARY KEY do?", "options": ["Allows NULL", "Uniquely identifies row", "Links tables", "Encrypts"], "answer": "B", "topic": "SQL"},
            {"q": "Graph with no cycles is called?", "options": ["Tree", "DAG", "Null Graph", "Complete Graph"], "answer": "A", "topic": "Graphs"},
            {"q": "Which keyword removes duplicates in SQL?", "options": ["UNIQUE", "FILTER", "DISTINCT", "NODUPE"], "answer": "C", "topic": "SQL"},
        ],
    },
}

SESSION_QUESTIONS = {}


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(cursor, table, column, definition):
    columns = [row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            player_name TEXT DEFAULT 'Anonymous',
            category TEXT,
            mode TEXT,
            score INTEGER DEFAULT 0,
            total INTEGER DEFAULT 10,
            accuracy REAL DEFAULT 0,
            avg_time REAL DEFAULT 0,
            room_code TEXT DEFAULT '',
            is_completed INTEGER DEFAULT 0,
            created_at INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            question TEXT,
            chosen TEXT,
            correct TEXT,
            is_correct INTEGER,
            time_taken INTEGER,
            topic TEXT,
            category TEXT DEFAULT '',
            player_name TEXT DEFAULT '',
            room_code TEXT DEFAULT '',
            explanation TEXT DEFAULT '',
            created_at INTEGER DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY,
            total_sessions INTEGER DEFAULT 0,
            total_answers INTEGER DEFAULT 0,
            total_correct INTEGER DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            code TEXT PRIMARY KEY,
            teacher_name TEXT DEFAULT 'Teacher',
            category TEXT DEFAULT '',
            title TEXT DEFAULT '',
            created_at INTEGER,
            updated_at INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS room_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT,
            player_name TEXT,
            role TEXT DEFAULT 'student',
            score INTEGER DEFAULT 0,
            answered INTEGER DEFAULT 0,
            accuracy REAL DEFAULT 0,
            joined_at INTEGER,
            last_seen INTEGER,
            UNIQUE(room_code, player_name)
        )
        """
    )
    ensure_column(cur, "sessions", "room_code", "TEXT DEFAULT ''")
    ensure_column(cur, "sessions", "is_completed", "INTEGER DEFAULT 0")
    ensure_column(cur, "answers", "category", "TEXT DEFAULT ''")
    ensure_column(cur, "answers", "player_name", "TEXT DEFAULT ''")
    ensure_column(cur, "answers", "room_code", "TEXT DEFAULT ''")
    ensure_column(cur, "answers", "explanation", "TEXT DEFAULT ''")
    ensure_column(cur, "answers", "created_at", "INTEGER DEFAULT 0")
    cur.execute("INSERT OR IGNORE INTO stats (id) VALUES (1)")
    conn.commit()
    conn.close()


init_db()


def now_ts():
    return int(time.time())


def make_room_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def infer_weak_topics(answer_rows):
    wrong_topics = Counter(row.get("topic") if isinstance(row, dict) else row["topic"] for row in answer_rows if not (row.get("ok") if isinstance(row, dict) else row["is_correct"]))
    return [topic for topic, _ in wrong_topics.most_common(3)]


def fallback_explanation(question, correct_answer, chosen, topic):
    picked = chosen or "no answer"
    return f"In topic {topic}, the correct answer is {correct_answer} because it directly fits '{question}'. Your choice was {picked}, so revise this core concept once before the next question."


def fallback_personalized_questions(weak_topics, category):
    topics = weak_topics or ["Core Concepts"]
    category_name = category or "this quiz"
    return [
        {
            "question": f"Practice {idx}: In {category_name}, which statement best demonstrates {topic}?",
            "focus_topic": topic,
            "why": f"Generated because {topic} appeared as a weak area.",
        }
        for idx, topic in enumerate(topics[:3], start=1)
    ]


def fallback_study_plan(weak_topics, accuracy):
    topics = weak_topics or ["foundational concepts"]
    return [
        f"Spend 15 minutes revising {topics[0]} with one worked example.",
        f"Attempt 5 fresh MCQs on {topics[min(1, len(topics) - 1)]}.",
        f"Do a timed recap quiz and target accuracy above {max(accuracy + 10, 70)}%.",
    ]


def call_groq(messages, temperature=0.3, max_tokens=500):
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None
    payload = json.dumps(
        {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        GROQ_API_URL,
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, json.JSONDecodeError):
        return None


def ai_json_response(task, user_payload, fallback):
    content = call_groq(
        [
            {"role": "system", "content": "You are a concise study coach. Return valid JSON only."},
            {"role": "user", "content": f"Task: {task}\nPayload:\n{json.dumps(user_payload)}"},
        ],
        temperature=0.4,
        max_tokens=700,
    )
    if not content:
        return fallback
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return fallback


def sync_member_stats(db, room_code_value, player_name):
    if not room_code_value or not player_name:
        return
    row = db.execute(
        """
        SELECT s.score AS score, COUNT(a.id) AS answered,
               COALESCE(ROUND(AVG(a.is_correct) * 100, 1), 0) AS accuracy
        FROM sessions s
        LEFT JOIN answers a ON a.session_id = s.id
        WHERE s.room_code=? AND s.player_name=?
        GROUP BY s.player_name, s.score
        ORDER BY s.created_at DESC
        LIMIT 1
        """,
        (room_code_value, player_name),
    ).fetchone()
    if row:
        db.execute(
            """
            INSERT INTO room_members (room_code, player_name, role, score, answered, accuracy, joined_at, last_seen)
            VALUES (?, ?, 'student', ?, ?, ?, ?, ?)
            ON CONFLICT(room_code, player_name)
            DO UPDATE SET score=excluded.score, answered=excluded.answered, accuracy=excluded.accuracy, last_seen=excluded.last_seen
            """,
            (room_code_value, player_name, row["score"] or 0, row["answered"] or 0, row["accuracy"] or 0, now_ts(), now_ts()),
        )


@app.route("/")
def home():
    return send_file("gesture_quiz.html")


@app.route("/api/categories", methods=["GET"])
def get_categories():
    cats = {}
    for cat_id, cat in QUESTION_BANK.items():
        cats[cat_id] = {"id": cat_id, "name": cat["name"], "emoji": cat["emoji"], "question_count": len(cat["questions"])}
    return jsonify({"success": True, "categories": cats})


@app.route("/api/ai/status", methods=["GET"])
def ai_status():
    return jsonify({"success": True, "configured": bool(os.getenv("GROQ_API_KEY", "").strip()), "model": GROQ_MODEL})


@app.route("/api/ai/explain", methods=["POST"])
def ai_explain():
    data = request.json or {}
    fallback = {"explanation": fallback_explanation(data.get("question", "this question"), data.get("correct_answer", "unknown"), data.get("chosen", ""), data.get("topic", "General"))}
    result = ai_json_response("Explain why the correct answer is right after a wrong attempt. Return {'explanation': string}.", data, fallback)
    return jsonify({"success": True, **result, "source": "groq" if result != fallback else "fallback"})


@app.route("/api/ai/personalize", methods=["POST"])
def ai_personalize():
    data = request.json or {}
    weak_topics = data.get("weak_topics") or []
    fallback = {"weak_topics": weak_topics, "questions": fallback_personalized_questions(weak_topics, data.get("category", ""))}
    result = ai_json_response("Detect weak topics and generate 3 personalized practice questions. Return {'weak_topics': [..], 'questions': [{'question': str, 'focus_topic': str, 'why': str}]}.", data, fallback)
    return jsonify({"success": True, **result, "source": "groq" if result != fallback else "fallback"})


@app.route("/api/ai/study-plan", methods=["POST"])
def ai_study_plan():
    data = request.json or {}
    weak_topics = data.get("weak_topics") or []
    fallback = {"study_plan": fallback_study_plan(weak_topics, int(data.get("accuracy", 0)))}
    result = ai_json_response("Generate a short 3-step study plan. Return {'study_plan': [string, string, string]}.", data, fallback)
    return jsonify({"success": True, **result, "source": "groq" if result != fallback else "fallback"})


@app.route("/api/session/register", methods=["POST"])
def register_session():
    data = request.json or {}
    session_id = str(uuid.uuid4())[:8].upper()
    player_name = data.get("player_name", "Anonymous")
    category = data.get("category", "")
    mode = data.get("mode", "finger")
    room_code_value = data.get("room_code", "")
    total = int(data.get("total", 10))
    db = get_db()
    db.execute("INSERT INTO sessions (id, player_name, category, mode, total, room_code, created_at) VALUES (?,?,?,?,?,?,?)", (session_id, player_name, category, mode, total, room_code_value, now_ts()))
    if room_code_value:
        db.execute(
            """
            INSERT INTO room_members (room_code, player_name, role, joined_at, last_seen)
            VALUES (?, ?, 'student', ?, ?)
            ON CONFLICT(room_code, player_name) DO UPDATE SET last_seen=excluded.last_seen
            """,
            (room_code_value, player_name, now_ts(), now_ts()),
        )
    db.commit()
    db.close()
    return jsonify({"success": True, "session_id": session_id})


@app.route("/api/session/answer-log", methods=["POST"])
def answer_log():
    data = request.json or {}
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"success": False, "error": "session_id required"}), 400
    db = get_db()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not session:
        db.close()
        return jsonify({"success": False, "error": "Session not found"}), 404
    is_correct = int(bool(data.get("is_correct")))
    db.execute(
        """
        INSERT INTO answers (session_id, question, chosen, correct, is_correct, time_taken, topic, category, player_name, room_code, explanation, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            data.get("question", ""),
            (data.get("chosen") or "").upper(),
            (data.get("correct_answer") or "").upper(),
            is_correct,
            int(data.get("time_taken", 0)),
            data.get("topic", ""),
            session["category"],
            session["player_name"],
            session["room_code"],
            data.get("explanation", ""),
            now_ts(),
        ),
    )
    if is_correct:
        db.execute("UPDATE sessions SET score = score + 1 WHERE id=?", (session_id,))
    db.execute("UPDATE stats SET total_answers = total_answers + 1, total_correct = total_correct + ? WHERE id=1", (is_correct,))
    sync_member_stats(db, session["room_code"], session["player_name"])
    db.commit()
    db.close()
    return jsonify({"success": True})


@app.route("/api/session/finalize", methods=["POST"])
def finalize_session():
    data = request.json or {}
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"success": False, "error": "session_id required"}), 400
    db = get_db()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    answers = db.execute("SELECT * FROM answers WHERE session_id=? ORDER BY id", (session_id,)).fetchall()
    if not session:
        db.close()
        return jsonify({"success": False, "error": "Session not found"}), 404
    score = session["score"]
    total = max(session["total"], 1)
    accuracy = round(score / total * 100, 1)
    avg_time = round(sum(a["time_taken"] for a in answers) / len(answers), 1) if answers else 0
    db.execute("UPDATE sessions SET accuracy=?, avg_time=?, is_completed=1 WHERE id=?", (accuracy, avg_time, session_id))
    db.execute("UPDATE stats SET total_sessions = total_sessions + 1 WHERE id=1")
    sync_member_stats(db, session["room_code"], session["player_name"])
    db.commit()
    db.close()
    return jsonify({"success": True, "session_id": session_id, "score": score, "total": total, "accuracy": accuracy, "avg_time": avg_time})


@app.route("/api/session/result/<session_id>", methods=["GET"])
def get_result(session_id):
    db = get_db()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not session:
        db.close()
        return jsonify({"success": False, "error": "Session not found"}), 404
    answers = db.execute("SELECT * FROM answers WHERE session_id=? ORDER BY id", (session_id,)).fetchall()
    db.close()
    score = session["score"]
    total = session["total"]
    accuracy = round(score / total * 100, 1) if total else 0
    avg_time = round(sum(a["time_taken"] for a in answers) / len(answers), 1) if answers else 0
    return jsonify({"success": True, "session_id": session_id, "player_name": session["player_name"], "category": session["category"], "mode": session["mode"], "score": score, "total": total, "accuracy": accuracy, "avg_time": avg_time, "weak_topics": infer_weak_topics([dict(a) for a in answers]), "answers": [dict(a) for a in answers]})


@app.route("/api/classroom/create", methods=["POST"])
def classroom_create():
    data = request.json or {}
    teacher_name = data.get("teacher_name", "Teacher")
    category = data.get("category", "")
    title = data.get("title", "Live Gesture Quiz Room")
    code = make_room_code()
    db = get_db()
    while db.execute("SELECT 1 FROM rooms WHERE code=?", (code,)).fetchone():
        code = make_room_code()
    db.execute("INSERT INTO rooms (code, teacher_name, category, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)", (code, teacher_name, category, title, now_ts(), now_ts()))
    db.execute(
        """
        INSERT INTO room_members (room_code, player_name, role, joined_at, last_seen)
        VALUES (?, ?, 'teacher', ?, ?)
        ON CONFLICT(room_code, player_name) DO UPDATE SET last_seen=excluded.last_seen
        """,
        (code, teacher_name, now_ts(), now_ts()),
    )
    db.commit()
    db.close()
    return jsonify({"success": True, "room_code": code, "teacher_name": teacher_name, "category": category, "title": title})


@app.route("/api/classroom/join", methods=["POST"])
def classroom_join():
    data = request.json or {}
    code = (data.get("room_code") or "").upper().strip()
    player_name = data.get("player_name", "Student")
    role = data.get("role", "student")
    if not code:
        return jsonify({"success": False, "error": "room_code required"}), 400
    db = get_db()
    room = db.execute("SELECT * FROM rooms WHERE code=?", (code,)).fetchone()
    if not room:
        db.close()
        return jsonify({"success": False, "error": "Room not found"}), 404
    db.execute(
        """
        INSERT INTO room_members (room_code, player_name, role, joined_at, last_seen)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(room_code, player_name) DO UPDATE SET role=excluded.role, last_seen=excluded.last_seen
        """,
        (code, player_name, role, now_ts(), now_ts()),
    )
    db.execute("UPDATE rooms SET updated_at=? WHERE code=?", (now_ts(), code))
    db.commit()
    db.close()
    return jsonify({"success": True, "room": dict(room), "player_name": player_name, "role": role})


@app.route("/api/classroom/heartbeat", methods=["POST"])
def classroom_heartbeat():
    data = request.json or {}
    code = (data.get("room_code") or "").upper().strip()
    player_name = data.get("player_name", "")
    if not code or not player_name:
        return jsonify({"success": False, "error": "room_code and player_name required"}), 400
    db = get_db()
    db.execute(
        """
        INSERT INTO room_members (room_code, player_name, role, joined_at, last_seen)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(room_code, player_name) DO UPDATE SET last_seen=excluded.last_seen
        """,
        (code, player_name, data.get("role", "student"), now_ts(), now_ts()),
    )
    db.commit()
    db.close()
    return jsonify({"success": True})


@app.route("/api/classroom/<code>/leaderboard", methods=["GET"])
def classroom_leaderboard(code):
    db = get_db()
    room = db.execute("SELECT * FROM rooms WHERE code=?", (code.upper(),)).fetchone()
    if not room:
        db.close()
        return jsonify({"success": False, "error": "Room not found"}), 404
    members = db.execute(
        """
        SELECT player_name, role, score, answered, accuracy, last_seen
        FROM room_members
        WHERE room_code=?
        ORDER BY role='teacher' DESC, score DESC, accuracy DESC, answered DESC, player_name ASC
        """,
        (code.upper(),),
    ).fetchall()
    recent_answers = db.execute(
        """
        SELECT player_name, question, is_correct, time_taken, created_at
        FROM answers
        WHERE room_code=?
        ORDER BY created_at DESC
        LIMIT 8
        """,
        (code.upper(),),
    ).fetchall()
    db.close()
    return jsonify({"success": True, "room": dict(room), "leaderboard": [dict(m) for m in members], "recent_answers": [dict(r) for r in recent_answers]})


@app.route("/api/dashboard/live", methods=["GET"])
def dashboard_live():
    room = request.args.get("room_code", "").upper().strip()
    db = get_db()
    answer_where = "WHERE room_code=?" if room else ""
    answer_params = [room] if room else []
    session_where = "WHERE room_code=?" if room else ""
    session_params = [room] if room else []
    hardest = db.execute(
        f"""
        SELECT question, topic, COUNT(*) AS attempts,
               SUM(CASE WHEN is_correct=0 THEN 1 ELSE 0 END) AS wrong_count,
               ROUND(100.0 * AVG(is_correct), 1) AS accuracy
        FROM answers
        {answer_where}
        GROUP BY question, topic
        HAVING COUNT(*) > 0
        ORDER BY accuracy ASC, attempts DESC
        LIMIT 1
        """,
        answer_params,
    ).fetchone()
    topic_times = db.execute(
        f"""
        SELECT topic, ROUND(AVG(time_taken), 1) AS avg_time, COUNT(*) AS attempts
        FROM answers
        {answer_where}
        GROUP BY topic
        ORDER BY avg_time DESC
        LIMIT 8
        """,
        answer_params,
    ).fetchall()
    perf_rows = db.execute(
        f"""
        SELECT player_name, score, accuracy
        FROM sessions
        {session_where}
        ORDER BY created_at DESC
        LIMIT 10
        """,
        session_params,
    ).fetchall()
    live_board = db.execute(
        f"""
        SELECT player_name, score, accuracy, avg_time
        FROM sessions
        {session_where}
        ORDER BY score DESC, accuracy DESC, avg_time ASC
        LIMIT 5
        """,
        session_params,
    ).fetchall()
    overall = db.execute("SELECT * FROM stats WHERE id=1").fetchone()
    db.close()
    perf_rows = list(reversed(perf_rows))
    return jsonify(
        {
            "success": True,
            "hardest_question": dict(hardest) if hardest else None,
            "avg_response_time_by_topic": [dict(r) for r in topic_times],
            "performance_graph": {
                "labels": [row["player_name"][:8] or f"S{i + 1}" for i, row in enumerate(perf_rows)],
                "scores": [row["score"] for row in perf_rows],
                "accuracy": [row["accuracy"] for row in perf_rows],
            },
            "live_leaderboard": [dict(r) for r in live_board],
            "totals": {
                "sessions": overall["total_sessions"] if overall else 0,
                "answers": overall["total_answers"] if overall else 0,
                "accuracy": round((overall["total_correct"] / overall["total_answers"]) * 100, 1) if overall and overall["total_answers"] else 0,
            },
        }
    )


@app.route("/api/stats", methods=["GET"])
def global_stats():
    db = get_db()
    stats = db.execute("SELECT * FROM stats WHERE id=1").fetchone()
    cat_stats = db.execute("SELECT category, COUNT(*) AS sessions, ROUND(AVG(score), 1) AS avg_score FROM sessions GROUP BY category ORDER BY sessions DESC").fetchall()
    db.close()
    total_answers = stats["total_answers"] if stats else 0
    total_correct = stats["total_correct"] if stats else 0
    return jsonify({"success": True, "total_sessions": stats["total_sessions"] if stats else 0, "total_answers": total_answers, "total_correct": total_correct, "overall_accuracy": round(total_correct / total_answers * 100, 1) if total_answers else 0, "category_breakdown": [dict(r) for r in cat_stats]})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": now_ts()})


if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    print("\n" + "=" * 50)
    print("GestureQuiz Pro - Backend Server")
    print("=" * 50)
    print(f"Running on: http://localhost:{port}")
    print("Database: gesturequiz.db")
    print("Groq configured:", bool(os.getenv("GROQ_API_KEY", "").strip()))
    print("=" * 50 + "\n")
    app.run(debug=debug, host="0.0.0.0", port=port)
