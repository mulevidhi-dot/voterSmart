from flask import Flask, render_template, request
import sqlite3
import os

app = Flask(__name__)

# Keep the database beside app.py so the path works locally and on Render.
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")

# Dictionary mapping raw answer codes (a, b, c, d) to full text labels
ANSWER_MAP = {
    "q1": {
        "a": "A — It is mandatory for all citizens",
        "b": "B — It allows citizens to participate in the democratic process",
        "c": "C — It guarantees financial rewards",
        "d": "D — It is only for political leaders"
    },
    "q2": {
        "a": "A — Official election sources",
        "b": "B — Unverified social media posts",
        "c": "C — Anonymous WhatsApp messages",
        "d": "D — Random blogs"
    },
    "q3": {
        "a": "a", "b": "b",
        "c": "C — Verify it using reliable sources",
        "d": "d"
    },
    "q4": {
        "a": "a",
        "b": "B — Someone who seeks reliable information",
        "c": "c", "d": "d"
    },
    "q5": {
        "a": "A — Having a Voter ID card only",
        "b": "B — Having your name registered in the official Electoral Roll",
        "c": "C — Having an Aadhaar card only",
        "d": "D — Having a driver's license only"
    }
}


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    # Feedback table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            message TEXT NOT NULL,
            rating INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Quiz table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            score INTEGER,
            total INTEGER,
            q1 TEXT,
            q2 TEXT,
            q3 TEXT,
            q4 TEXT,
            q5 TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Schema migration for existing tables
    existing_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(quiz_results)").fetchall()
    }

    for column in ["q1", "q2", "q3", "q4", "q5"]:
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE quiz_results ADD COLUMN {column} TEXT")

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/voter-guide")
def voter_guide():
    return render_template("voter_guide.html")


@app.route("/rights")
def rights():
    return render_template("rights.html")


@app.route("/misinformation")
def misinformation():
    return render_template("misinformation.html")


@app.route("/quiz")
def quiz():
    return render_template("quiz.html")


@app.route("/quiz-result", methods=["POST"])
def quiz_result():
    name = request.form.get("name", "Anonymous").strip() or "Anonymous"

    questions = ["q1", "q2", "q3", "q4", "q5"]

    correct_answers = {
        "q1": "b",
        "q2": "a",
        "q3": "c",
        "q4": "b",
        "q5": "b"
    }

    answers = {question: request.form.get(question, "").lower() for question in questions}
    score = sum(
        1 for question in questions
        if answers[question] == correct_answers[question]
    )

    conn = get_db()
    conn.execute(
        """
        INSERT INTO quiz_results
        (name, score, total, q1, q2, q3, q4, q5)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            score,
            len(questions),
            answers["q1"],
            answers["q2"],
            answers["q3"],
            answers["q4"],
            answers["q5"]
        )
    )
    conn.commit()
    conn.close()

    percentage = round((score / len(questions)) * 100, 1)

    return render_template(
        "result.html",
        name=name,
        score=score,
        total=len(questions),
        percentage=percentage
    )


@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()
        rating = request.form.get("rating")

        conn = get_db()
        conn.execute(
            """
            INSERT INTO feedback
            (name, email, message, rating)
            VALUES (?, ?, ?, ?)
            """,
            (name, email, message, rating)
        )
        conn.commit()
        conn.close()

        return render_template("feedback.html", submitted=True)

    return render_template("feedback.html", submitted=False)


@app.route("/admin")
def admin():
    conn = get_db()

    feedback_count = conn.execute(
        "SELECT COUNT(*) FROM feedback"
    ).fetchone()[0]

    quiz_count = conn.execute(
        "SELECT COUNT(*) FROM quiz_results"
    ).fetchone()[0]

    raw_results = conn.execute(
        """
        SELECT *
        FROM quiz_results
        ORDER BY created_at DESC
        """
    ).fetchall()

    # Convert raw stored answers (a, b, c, d) into full text labels for display
    formatted_results = []
    for row in raw_results:
        row_dict = dict(row)
        for q in ["q1", "q2", "q3", "q4", "q5"]:
            raw_val = row_dict.get(q, "")
            row_dict[q] = ANSWER_MAP.get(q, {}).get(raw_val, raw_val.upper())
        formatted_results.append(row_dict)

    feedbacks = conn.execute(
        """
        SELECT *
        FROM feedback
        ORDER BY created_at DESC
        """
    ).fetchall()

    # Rating statistics for the feedback graph
    rating_stats = []
    for rating in range(5, 0, -1):
        count = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE rating = ?",
            (rating,)
        ).fetchone()[0]
        percentage = round((count * 100.0) / feedback_count, 1) if feedback_count else 0
        rating_stats.append({
            "rating": rating,
            "count": count,
            "percentage": percentage
        })

    average_rating = conn.execute(
        "SELECT AVG(rating) FROM feedback WHERE rating IS NOT NULL"
    ).fetchone()[0]
    average_rating = round(average_rating, 1) if average_rating is not None else 0

    conn.close()

    return render_template(
        "admin.html",
        feedback_count=feedback_count,
        quiz_count=quiz_count,
        results=formatted_results,
        feedbacks=feedbacks,
        rating_stats=rating_stats,
        average_rating=average_rating
    )


# Initialize DB tables
init_db()


if __name__ == "__main__":
    app.run(debug=True)
