from flask import Flask, render_template, request
import psycopg2
from psycopg2.extras import RealDictCursor
import os

app = Flask(__name__)

# Fetch database connection URL from Render environment variables or local fallback
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/votersmart")

# Complete mapping dictionary for transforming raw choices into descriptive labels
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
        "a": "A — Believe it immediately",
        "b": "B — Forward it to all your contacts",
        "c": "C — Verify it using reliable sources",
        "d": "D — Ignore official sources"
    },
    "q4": {
        "a": "A — Someone who spreads unverified news",
        "b": "B — Someone who seeks reliable information",
        "c": "C — Someone who ignores elections completely",
        "d": "D — Someone who votes based on rumours"
    },
    "q5": {
        "a": "A — Having a Voter ID card only",
        "b": "B — Having your name registered in the official Electoral Roll",
        "c": "C — Having an identity card only",
        "d": "D — Having a driver's license only"
    }
}


def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Feedback table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            message TEXT NOT NULL,
            rating INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Quiz table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quiz_results (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            score INTEGER,
            total INTEGER,
            q1 TEXT,
            q2 TEXT,
            q3 TEXT,
            q4 TEXT,
            q5 TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    cur.close()
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

    answers = {question: request.form.get(question, "").strip().lower() for question in questions}
    score = sum(
        1 for question in questions
        if answers[question] == correct_answers[question]
    )

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO quiz_results
        (name, score, total, q1, q2, q3, q4, q5)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
    cur.close()
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

        # Convert rating to int if present
        rating_val = int(rating) if rating and rating.isdigit() else None

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO feedback
            (name, email, message, rating)
            VALUES (%s, %s, %s, %s)
            """,
            (name, email, message, rating_val)
        )
        conn.commit()
        cur.close()
        conn.close()

        return render_template("feedback.html", submitted=True)

    return render_template("feedback.html", submitted=False)


@app.route("/admin")
def admin():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS count FROM feedback")
    feedback_count = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) AS count FROM quiz_results")
    quiz_count = cur.fetchone()["count"]

    cur.execute(
        """
        SELECT *
        FROM quiz_results
        ORDER BY created_at DESC
        """
    )
    raw_results = cur.fetchall()

    # Safely convert raw answers to full text labels
    formatted_results = []
    for row in raw_results:
        row_dict = dict(row)
        for q in ["q1", "q2", "q3", "q4", "q5"]:
            raw_val = row_dict.get(q)
            if raw_val:
                raw_val_str = str(raw_val).lower()
                row_dict[q] = ANSWER_MAP.get(q, {}).get(raw_val_str, raw_val_str.upper())
            else:
                row_dict[q] = "Not recorded for this older attempt"
        formatted_results.append(row_dict)

    cur.execute(
        """
        SELECT *
        FROM feedback
        ORDER BY created_at DESC
        """
    )
    feedbacks = cur.fetchall()

    # Rating statistics calculation
    rating_stats = []
    for rating in range(5, 0, -1):
        cur.execute(
            "SELECT COUNT(*) AS count FROM feedback WHERE rating = %s",
            (rating,)
        )
        count = cur.fetchone()["count"]
        percentage = round((count * 100.0) / feedback_count, 1) if feedback_count else 0
        rating_stats.append({
            "rating": rating,
            "count": count,
            "percentage": percentage
        })

    cur.execute("SELECT AVG(rating) AS avg FROM feedback WHERE rating IS NOT NULL")
    avg_row = cur.fetchone()
    average_rating = round(avg_row["avg"], 1) if avg_row and avg_row["avg"] is not None else 0

    cur.close()
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


# Ensure database tables exist on startup
init_db()


if __name__ == "__main__":
    app.run(debug=True)
