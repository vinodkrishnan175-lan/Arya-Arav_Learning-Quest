import random
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st

APP_TITLE = "Arya & Arav Learning Quest"
DB_PATH = Path("learning_quest.db")
WEEKLY_GOAL = 900
CHILD_TARGET = 450
QUESTION_TARGET = 28
SESSION_MINUTES = 45

THEME_PLAN = [
    "Rivers of the World",
    "Mountains and Peaks",
    "Forests and Trees",
    "Oceans and Seas",
    "Weather and Clouds",
    "Deserts",
    "Islands",
    "Animals of the Jungle",
    "Birds and Flight",
    "Insects and Small Creatures",
    "The Arctic and Antarctic",
    "Volcanoes and Earthquakes",
    "The Water Cycle",
    "Ancient Civilizations",
    "Explorers and Voyages",
    "Great Cities of the World",
    "Life in Villages",
    "Transportation",
    "Bridges and Buildings",
    "Markets and Trade",
    "Food Around the World",
    "Festivals and Traditions",
    "Famous Inventions",
    "Maps and Navigation",
    "Languages of the World",
    "Famous Landmarks",
    "Plants and Growth",
    "The Human Body",
    "Energy and Electricity",
    "Light and Shadows",
    "Sound and Music",
    "Magnets and Forces",
    "Machines",
    "The Solar System",
    "Gravity",
    "Water and Ice",
    "Air and Wind",
    "Simple Chemistry",
    "Technology Around Us",
    "Space Exploration",
    "Planets",
    "Stars and Galaxies",
    "The Moon",
    "Time and Calendars",
    "Famous Scientists",
    "Ocean Exploration",
    "Robots and AI",
    "Climate and Earth",
    "Mysteries of the Deep Sea",
    "The Future of Cities",
    "The History of Earth",
    "Review and Grand Challenge Week",
]

CHILDREN = {
    "Arya": {
        "age": 10,
        "difficulty": "arya",
        "intro": "calm, thoughtful, slightly deeper questions",
    },
    "Arav": {
        "age": 8,
        "difficulty": "arav",
        "intro": "shorter, concrete, playful-but-not-childish questions",
    },
}

SUBJECT_ORDER = [
    ("Math", 8),
    ("English", 6),
    ("Geography", 5),
    ("Science", 4),
    ("Logic", 3),
    ("Reflection", 2),
]


@dataclass
class Question:
    qid: str
    subject: str
    qtype: str
    prompt: str
    options: List[str]
    answer: str
    explanation: str
    points_correct: int = 4
    points_incorrect: int = 0
    points_completed: int = 3

    def to_dict(self) -> Dict:
        return self.__dict__


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child TEXT NOT NULL,
            day TEXT NOT NULL,
            week_start TEXT NOT NULL,
            theme TEXT NOT NULL,
            score_pct REAL NOT NULL,
            points INTEGER NOT NULL,
            attempted INTEGER NOT NULL,
            correct_count INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            remaining_questions INTEGER NOT NULL,
            session_minutes INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(child, day)
        )
        """
    )
    conn.commit()
    conn.close()


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_theme(d: date) -> str:
    start = date(d.year, 1, 1)
    week_index = ((d - monday_of(start)).days // 7) % len(THEME_PLAN)
    return THEME_PLAN[week_index]


def weekly_points(week_start: date) -> Dict[str, int]:
    conn = get_conn()
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT child, COALESCE(SUM(points),0) AS pts FROM sessions WHERE week_start = ? GROUP BY child",
        (week_start.isoformat(),),
    ).fetchall()
    conn.close()
    totals = {"Arya": 0, "Arav": 0}
    for row in rows:
        totals[row["child"]] = int(row["pts"])
    return totals


def weekly_stats(week_start: date) -> Dict[str, Dict[str, int]]:
    conn = get_conn()
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT child,
               COALESCE(SUM(points),0) AS pts,
               COALESCE(SUM(attempted),0) AS attempted,
               ROUND(COALESCE(AVG(score_pct),0), 1) AS avg_score,
               COALESCE(SUM(remaining_questions),0) AS remaining,
               COUNT(*) as sessions_count
        FROM sessions
        WHERE week_start = ?
        GROUP BY child
        """,
        (week_start.isoformat(),),
    ).fetchall()
    conn.close()
    out = {
        "Arya": {"pts": 0, "attempted": 0, "avg_score": 0, "remaining": 0, "sessions_count": 0},
        "Arav": {"pts": 0, "attempted": 0, "avg_score": 0, "remaining": 0, "sessions_count": 0},
    }
    for row in rows:
        out[row["child"]] = {
            "pts": int(row["pts"]),
            "attempted": int(row["attempted"]),
            "avg_score": float(row["avg_score"]),
            "remaining": int(row["remaining"]),
            "sessions_count": int(row["sessions_count"]),
        }
    return out


def last_session(child: str) -> Optional[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT * FROM sessions WHERE child = ? ORDER BY day DESC LIMIT 1",
        (child,),
    ).fetchone()
    conn.close()
    return row


def streak(child: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT day FROM sessions WHERE child = ? ORDER BY day DESC",
        (child,),
    ).fetchall()
    conn.close()
    done_days = {date.fromisoformat(r["day"]) for r in rows}
    today = date.today()
    cursor = today
    if cursor.weekday() >= 5:
        while cursor.weekday() >= 5:
            cursor -= timedelta(days=1)
    count = 0
    while cursor.weekday() < 5 and cursor in done_days:
        count += 1
        cursor -= timedelta(days=1)
        while cursor.weekday() >= 5:
            cursor -= timedelta(days=1)
    return count


def save_session(result: Dict) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO sessions (
            id, child, day, week_start, theme, score_pct, points, attempted,
            correct_count, total_questions, remaining_questions, session_minutes, created_at
        ) VALUES (
            COALESCE((SELECT id FROM sessions WHERE child = ? AND day = ?), NULL),
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            result["child"],
            result["day"],
            result["child"],
            result["day"],
            result["week_start"],
            result["theme"],
            result["score_pct"],
            result["points"],
            result["attempted"],
            result["correct_count"],
            result["total_questions"],
            result["remaining_questions"],
            result["session_minutes"],
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()


def deterministic_rng(child: str, day: date, theme: str) -> random.Random:
    seed = f"{child}-{day.isoformat()}-{theme}"
    return random.Random(seed)


def mcq(qid: str, subject: str, prompt: str, options: List[str], answer: str, explanation: str) -> Question:
    return Question(qid=qid, subject=subject, qtype="mcq", prompt=prompt, options=options, answer=answer, explanation=explanation)


def text_q(qid: str, subject: str, prompt: str, answer: str, explanation: str, reflection: bool = False) -> Question:
    return Question(qid=qid, subject=subject, qtype="reflection" if reflection else "text", prompt=prompt, options=[], answer=answer, explanation=explanation)


def gen_math(rng: random.Random, child: str, idx: int, theme: str) -> Question:
    hard = child == "Arya"
    if idx % 4 == 0:
        a = rng.randint(4, 12 if not hard else 18)
        b = rng.randint(3, 10 if not hard else 12)
        ans = a * b
        prompt = f"A {theme.lower().split()[0]} guide arranges {a} rows of {b} items. How many items are there in all?"
        expl = f"Multiply the number of rows by the number in each row: {a} × {b} = {ans}."
        return text_q(f"math-{idx}", "Math", prompt, str(ans), expl)
    if idx % 4 == 1:
        a = rng.randint(20, 80 if not hard else 160)
        b = rng.randint(5, 20 if not hard else 45)
        ans = a + b
        opts = [str(ans - rng.randint(2, 9)), str(ans), str(ans + rng.randint(2, 9))]
        rng.shuffle(opts)
        prompt = f"A traveller covered {a} km in the morning and {b} km later. How far altogether?"
        expl = f"Add the two distances: {a} + {b} = {ans} km."
        return mcq(f"math-{idx}", "Math", prompt, opts, str(ans), expl)
    if idx % 4 == 2:
        base = rng.randint(2, 9)
        seq = [base * n for n in range(1, 5)]
        ans = base * 5
        prompt = f"Complete the pattern: {', '.join(map(str, seq))}, __"
        expl = f"The pattern goes up by {base} each time, so the next number is {ans}."
        return text_q(f"math-{idx}", "Math", prompt, str(ans), expl)
    total_mins = rng.choice([30, 45, 60, 75, 90])
    if hard:
        extra = rng.choice([15, 20, 25])
        ans = total_mins + extra
        prompt = f"A study walk lasts {total_mins} minutes, then another {extra} minutes. How many minutes altogether?"
        expl = f"Add the minutes: {total_mins} + {extra} = {ans}."
    else:
        hrs = total_mins // 60
        mins = total_mins % 60
        ans = total_mins
        prompt = f"How many minutes are there in {hrs} hour and {mins} minutes?"
        expl = f"One hour is 60 minutes. So {hrs} hour and {mins} minutes = {60 * hrs} + {mins} = {ans}."
    return text_q(f"math-{idx}", "Math", prompt, str(ans), expl)


def gen_english(rng: random.Random, child: str, idx: int, theme: str) -> Question:
    theme_word = theme.split()[0].lower()
    if idx % 3 == 0:
        words = ["gentle", "curious", "quiet", "bright", "wide"]
        ans = rng.choice(words)
        wrong = [w for w in words if w != ans][:2]
        opts = wrong + [ans]
        rng.shuffle(opts)
        prompt = f"Choose the word that best completes the sentence: The {theme_word} morning felt ___ and calm."
        expl = f"'{ans}' fits the mood of a calm morning best in this sentence."
        return mcq(f"eng-{idx}", "English", prompt, opts, ans, expl)
    if idx % 3 == 1:
        ans = "is" if child == "Arav" else "were"
        if child == "Arav":
            prompt = "Choose the correct word: The river ___ flowing after the rain."
            expl = "'River' is singular, so 'is' is the correct helping verb."
            opts = ["is", "are", "am"]
            return mcq(f"eng-{idx}", "English", prompt, opts, ans, expl)
        prompt = "Choose the correct word: The travellers ___ excited to see the mountains."
        expl = "'Travellers' is plural, so 'were' is the correct helping verb."
        opts = ["was", "were", "is"]
        return mcq(f"eng-{idx}", "English", prompt, opts, ans, expl)
    prompt = f"Write one vivid sentence using the word '{theme_word}'."
    expl = f"A vivid sentence helps the reader picture, hear, or feel something about {theme_word}."
    return text_q(f"eng-{idx}", "English", prompt, "Any thoughtful sentence using the word.", expl, reflection=True)


def gen_geography(rng: random.Random, child: str, idx: int, theme: str) -> Question:
    items = [
        ("Brazil", "South America", "Brazil is in South America and is home to much of the Amazon rainforest."),
        ("Kenya", "Africa", "Kenya is in East Africa and is known for savannas and wildlife."),
        ("Japan", "Asia", "Japan is an island nation in East Asia."),
        ("France", "Europe", "France is in Western Europe."),
    ]
    country, ans, expl = items[idx % len(items)]
    opts = ["Asia", "Africa", "Europe", "South America"]
    rng.shuffle(opts)
    if ans not in opts:
        opts[0] = ans
    prompt = f"Which continent is {country} in?"
    return mcq(f"geo-{idx}", "Geography", prompt, opts[:3] if child == "Arav" else opts[:4], ans, expl)


def gen_science(rng: random.Random, child: str, idx: int, theme: str) -> Question:
    bank = [
        ("Why do plants need sunlight?", ["To make food", "To make rocks", "To become taller than houses"], "To make food", "Plants use sunlight to make food, which helps them grow."),
        ("Why do shadows change during the day?", ["Because the Sun appears in different positions", "Because the ground moves faster", "Because trees stop growing"], "Because the Sun appears in different positions", "As the Sun appears to move across the sky, the angle of light changes, so shadows change too."),
        ("What does a seed need to begin growing?", ["Water", "Plastic", "Metal"], "Water", "Water helps wake up the seed and start growth."),
        ("Why is it cooler on high mountains?", ["The air is thinner and holds less heat", "Mountains block all sunlight", "Clouds make the rocks colder forever"], "The air is thinner and holds less heat", "Higher places often feel cooler because the air is thinner and less able to hold heat."),
    ]
    prompt, opts, ans, expl = bank[idx % len(bank)]
    return mcq(f"sci-{idx}", "Science", prompt, opts, ans, expl)


def gen_logic(rng: random.Random, child: str, idx: int, theme: str) -> Question:
    if idx % 2 == 0:
        seq = [2, 4, 8, 16]
        ans = "32"
        expl = "Each number is double the one before it, so 16 becomes 32."
        return text_q(f"logic-{idx}", "Logic", f"What comes next? {', '.join(map(str, seq))}, __", ans, expl)
    prompt = "Which one does not belong: camel, tiger, dolphin, lion?"
    ans = "dolphin"
    expl = "A dolphin lives in water, while the others are land mammals."
    return text_q(f"logic-{idx}", "Logic", prompt, ans, expl)


def gen_reflection(rng: random.Random, child: str, idx: int, theme: str) -> Question:
    prompt = f"Imagine you are exploring {theme.lower()}. Write 1-2 thoughtful lines about what you notice."
    expl = "There is no single correct answer. The goal is to observe carefully and express an idea clearly."
    return text_q(f"reflect-{idx}", "Reflection", prompt, "Completed thoughtful response", expl, reflection=True)


def generate_questions(child: str, day: date, theme: str) -> List[Question]:
    rng = deterministic_rng(child, day, theme)
    questions: List[Question] = []
    generators = {
        "Math": gen_math,
        "English": gen_english,
        "Geography": gen_geography,
        "Science": gen_science,
        "Logic": gen_logic,
        "Reflection": gen_reflection,
    }
    for subject, count in SUBJECT_ORDER:
        for i in range(count):
            questions.append(generators[subject](rng, child, i, theme))
    return questions


def start_session(child: str) -> None:
    today = date.today()
    theme = week_theme(today)
    questions = generate_questions(child, today, theme)
    st.session_state.current_child = child
    st.session_state.theme = theme
    st.session_state.questions = [q.to_dict() for q in questions]
    st.session_state.answers = {}
    st.session_state.index = 0
    st.session_state.started = True
    st.session_state.completed = False
    st.session_state.session_start = datetime.now().isoformat()


def grade_session() -> Dict:
    child = st.session_state.current_child
    questions = st.session_state.questions
    answers = st.session_state.answers
    attempted = 0
    correct = 0
    points = 0
    reviewed = []
    for q in questions:
        user_answer = answers.get(q["qid"], "")
        is_reflection = q["qtype"] == "reflection"
        is_answered = bool(str(user_answer).strip())
        if is_answered:
            attempted += 1
        if is_reflection and is_answered:
            earned = q["points_completed"]
            points += earned
            reviewed.append({**q, "user_answer": user_answer, "was_correct": None, "points": earned})
            continue
        if is_answered and str(user_answer).strip().lower() == str(q["answer"]).strip().lower():
            correct += 1
            points += q["points_correct"]
            reviewed.append({**q, "user_answer": user_answer, "was_correct": True, "points": q["points_correct"]})
        else:
            reviewed.append({**q, "user_answer": user_answer, "was_correct": False if is_answered else None, "points": 0})
    if attempted >= max(20, len(questions) - 3):
        points += 10
    non_reflection_scored = len([q for q in questions if q["qtype"] != "reflection"])
    score_pct = round((correct / non_reflection_scored) * 100, 1) if non_reflection_scored else 0.0
    return {
        "child": child,
        "day": date.today().isoformat(),
        "week_start": monday_of(date.today()).isoformat(),
        "theme": st.session_state.theme,
        "attempted": attempted,
        "correct_count": correct,
        "total_questions": len(questions),
        "remaining_questions": len(questions) - attempted,
        "score_pct": score_pct,
        "points": points,
        "session_minutes": SESSION_MINUTES,
        "reviewed": reviewed,
    }


st.set_page_config(page_title=APP_TITLE, page_icon="📚", layout="wide")
init_db()

st.markdown(
    """
    <style>
    .hero {padding: 1rem 1.2rem; border-radius: 20px; background: linear-gradient(135deg, #0f2745, #1f513f); color: white;}
    .stat-card {padding: 1rem; border-radius: 18px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);}
    .question-card {padding: 1.2rem; border-radius: 18px; background: #111827; border: 1px solid #243041;}
    .tiny {font-size: 0.9rem; opacity: 0.85;}
    </style>
    """,
    unsafe_allow_html=True,
)

if "started" not in st.session_state:
    st.session_state.started = False
if "completed" not in st.session_state:
    st.session_state.completed = False


with st.sidebar:
    st.title("Navigation")
    page = st.radio("Go to", ["Home", "Parent Corner"], label_visibility="collapsed")
    st.caption("MVP built for Streamlit Community Cloud.")


def render_home() -> None:
    today = date.today()
    week_start = monday_of(today)
    theme = week_theme(today)
    totals = weekly_points(week_start)
    stats = weekly_stats(week_start)
    family_total = totals["Arya"] + totals["Arav"]
    unlocked = family_total >= WEEKLY_GOAL

    st.markdown(
        f"<div class='hero'><h1>{APP_TITLE}</h1><p>This week's theme: <b>{theme}</b></p><p>Weekly family goal: <b>{family_total} / {WEEKLY_GOAL}</b> points {'🎮 Reward unlocked' if unlocked else '🎮 Weekend reward locked'}</p></div>",
        unsafe_allow_html=True,
    )
    st.progress(min(family_total / WEEKLY_GOAL, 1.0))

    st.subheader("Today's Quests")
    cols = st.columns(2)
    for col, child in zip(cols, ["Arya", "Arav"]):
        with col:
            row = last_session(child)
            y_score = f"{row['score_pct']}%" if row else "—"
            y_questions = row["attempted"] if row else 0
            st.markdown(f"### {child}")
            st.markdown(
                f"<div class='stat-card'>Yesterday score: <b>{y_score}</b><br/>Questions completed: <b>{y_questions}</b><br/>Streak: 🔥 <b>{streak(child)}</b> days</div>",
                unsafe_allow_html=True,
            )
            if st.button(f"Start {child}'s Quest", key=f"start-{child}"):
                start_session(child)
                st.rerun()

    st.subheader("Weekly Progress")
    cols = st.columns(2)
    for col, child in zip(cols, ["Arya", "Arav"]):
        s = stats[child]
        approx_remaining = max(0, 5 * QUESTION_TARGET - s["attempted"])
        with col:
            st.markdown(
                f"<div class='stat-card'><h4>{child}</h4>"
                f"Points: <b>{s['pts']} / {CHILD_TARGET}</b><br/>"
                f"Questions completed: <b>{s['attempted']}</b><br/>"
                f"Remaining questions (approx): <b>{approx_remaining}</b><br/>"
                f"Average score: <b>{s['avg_score']}%</b></div>",
                unsafe_allow_html=True,
            )

    st.subheader("Explore")
    e1, e2, e3 = st.columns(3)
    e1.info("🌍 Country of the Week\n\nKenya")
    e2.info("🧠 Brain Puzzle\n\nWhat comes next: 3, 6, 12, 24, ?")
    e3.info("🌿 Nature Fact\n\nTrees release oxygen into the air.")


def render_parent_corner() -> None:
    today = date.today()
    week_start = monday_of(today)
    stats = weekly_stats(week_start)
    st.title("Parent Corner")
    st.caption("Daily and weekly performance overview")
    cols = st.columns(2)
    for col, child in zip(cols, ["Arya", "Arav"]):
        with col:
            row = last_session(child)
            st.markdown(f"### {child}")
            if row:
                st.markdown(
                    f"<div class='stat-card'>Today / Last Session<br/>"
                    f"Questions attempted: <b>{row['attempted']}</b><br/>"
                    f"Correct: <b>{row['correct_count']}</b><br/>"
                    f"Score: <b>{row['score_pct']}%</b><br/>"
                    f"Time: <b>{row['session_minutes']} min</b><br/>"
                    f"Points earned: <b>{row['points']}</b></div>",
                    unsafe_allow_html=True,
                )
            s = stats[child]
            st.markdown(
                f"<div class='stat-card' style='margin-top:0.75rem'>Weekly<br/>"
                f"Points: <b>{s['pts']}</b><br/>"
                f"Questions answered: <b>{s['attempted']}</b><br/>"
                f"Average score: <b>{s['avg_score']}%</b><br/>"
                f"Approx. remaining questions: <b>{max(0, 5*QUESTION_TARGET - s['attempted'])}</b></div>",
                unsafe_allow_html=True,
            )


def render_question_flow() -> None:
    child = st.session_state.current_child
    questions = st.session_state.questions
    idx = st.session_state.index
    total = len(questions)

    if st.session_state.completed:
        result = st.session_state.result
        st.title(f"Great work, {child}!")
        a, b, c, d = st.columns(4)
        a.metric("Questions attempted", result["attempted"])
        b.metric("Correct answers", result["correct_count"])
        c.metric("Score", f"{result['score_pct']}%")
        d.metric("Points today", result["points"])
        st.subheader("Review Answers")
        for item in result["reviewed"]:
            with st.expander(f"{item['subject']}: {item['prompt'][:90]}"):
                st.write(f"**Your answer:** {item['user_answer'] or 'Not answered'}")
                st.write(f"**Correct answer:** {item['answer']}")
                st.write(f"**Explanation:** {item['explanation']}")
        st.subheader("Today you explored")
        st.write(
            "• A theme-based mix of maths, language, world knowledge, science, and logic.\n"
            "• Review-based learning with clear explanations.\n"
            "• A steady weekly march toward the weekend gaming reward."
        )
        if st.button("Return Home"):
            st.session_state.started = False
            st.session_state.completed = False
            st.rerun()
        return

    q = questions[idx]
    done = len([a for a in st.session_state.answers.values() if str(a).strip()])
    points_live = 0

    st.markdown(
        f"<div class='hero'><h2>{child}'s Quest</h2><p>Theme: <b>{st.session_state.theme}</b></p><p>Time remaining: <b>{SESSION_MINUTES}:00</b> · Questions completed: <b>{done} / {total}</b> · Points so far: <b>{points_live}</b></p></div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<div class='question-card'><div class='tiny'>{q['subject']}</div><h3>{q['prompt']}</h3></div>",
        unsafe_allow_html=True,
    )

    existing = st.session_state.answers.get(q["qid"], "")
    if q["qtype"] == "mcq":
        ans = st.radio(
            "Choose one",
            q["options"],
            index=q["options"].index(existing) if existing in q["options"] else None,
            key=f"q-{q['qid']}",
        )
        st.session_state.answers[q["qid"]] = ans
    else:
        ans = st.text_input("Your answer", value=existing, key=f"q-{q['qid']}")
        st.session_state.answers[q["qid"]] = ans

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Previous", disabled=idx == 0):
            st.session_state.index -= 1
            st.rerun()
    with c2:
        if idx < total - 1:
            if st.button("Next"):
                st.session_state.index += 1
                st.rerun()
        else:
            if st.button("Finish Quest"):
                result = grade_session()
                save_session(result)
                st.session_state.result = result
                st.session_state.completed = True
                st.rerun()
    with c3:
        if st.button("End Now"):
            result = grade_session()
            save_session(result)
            st.session_state.result = result
            st.session_state.completed = True
            st.rerun()


if st.session_state.started:
    render_question_flow()
else:
    if page == "Home":
        render_home()
    else:
        render_parent_corner()
