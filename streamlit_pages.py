from batch_manager import get_eval_batch_size
import streamlit as st
import random
import os.path as osp
import io
from fpdf import FPDF
import json
from response_handler import fetch_all_responses
from config import CRITERIA, MODEL_LIST, DEBUG_MODE, VIDEO_ROOT, VIDEO_LENGTH, get_combo


def get_rankings(sorted_videos):
    scores = {model: 0 for model in MODEL_LIST}
    for i, video in enumerate(sorted_videos):
        scores[video] = i + 1
    return scores


def start_page():
    st.title("TTT Video-evaluation")
    st.markdown(f"#### Warning, please only use Google Chrome as your browser if you are not already doing so!")
    st.markdown(f"#### Welcome!")
    st.markdown("Please follow the instructions below to complete the evaluation.")

    st.markdown(
        f"""
                * You will make **{get_eval_batch_size()} comparisons** by watching `4`x {VIDEO_LENGTH}-second videos generated from the same text prompt.
                * You will rank them based on the specific criterion assigned for the comparison.

                The estimated time for this task is 2 to 3 hours. Criterion will be randomly selected from the following five options:"""
    )

    for i, criterion in CRITERIA.items():
        with st.expander(f"**{criterion[0]}**: {criterion[1]}", expanded=True):
            if criterion[2]:
                st.write(f"Violation example: {criterion[2]}")
            good_example_video = osp.join("example_videos", f"criterion{i}-good.mp4")
            bad_example_video = osp.join("example_videos", f"criterion{i}-bad.mp4")
            reason_text = osp.join("example_videos", f"criterion{i}-reason.txt")
            if osp.exists(good_example_video):
                with open(reason_text) as f:
                    reason_text = f.read()
                col1, col2 = st.columns(2)
                with col1:
                    st.caption("Good example👍")
                    st.video(good_example_video, start_time=0, format="video/mp4")
                with col2:
                    st.caption("Bad example👎")
                    st.video(bad_example_video, start_time=0, format="video/mp4")

                st.caption(f"{reason_text}")

    st.write("*The description of the criterion will be displayed again, no need to worry about memorizing it.*")
    st.markdown("### Instructions")
    st.markdown(
        """
                1. Watch all four videos considering the given criteria. *Our monitoring system will flag your submission if you do not watch the entire duration of all four videos.* 

                2. If necessary for evaluation based on the criteria(e.g. Text following), the prompts that generated the four videos will be displayed. Please read the prompts carefully

                3. Rank them based on the provided criterion; **focus strictly on this criterion** WITHOUT taking into account any other criteria or personal preferences. **1 for the best video and 4 for the worst video**.

                4. Feel free to watch the videos as many times as you need to make the best choice. However, you will NOT be able to return to the previous question after pressing the **[ Next ]** button.

                """
    )
    st.markdown("Please confirm the following:")

    checked = [False] * 3
    checked[0] = st.checkbox(
        "I am aware that marking a **smaller** number means a **better** video: 1 is the best, 4 is the worst."
    )
    checked[1] = st.checkbox(
        "I will watch all videos in their entirety and read the text prompt before making a decision."
    )
    checked[2] = st.checkbox("I will be thoughtful and make my best judgment before finalizing any decisions.")

    st.markdown("If you are ready, click the **[ Start ]** button below to begin.")
    st.warning("Please do not click start unless you fully commit to finishing this set of evaluation.")
    return all(checked)


def success_final_page(user_id, evals):
    st.success(
        f"User-{user_id:03d} have completed all evaluations.\n To download your receipt as **proof of completion**, simply click the button below. Thank you for your participation! Note: Once you leave this page, you cannot return."
    )

    evals = sorted(evals, key=lambda x: x[2])

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(0, 10, f"Receipt for user{user_id:03d}", ln=True)
    for row in evals:
        pdf.cell(0, 10, " ".join([str(item) for item in row[2:]]), ln=True)

    pdf_buffer = io.BytesIO()
    pdf_buffer.write(pdf.output(dest="S").encode("latin1"))
    pdf_buffer.seek(0)

    st.download_button(
        label="📥 Download Receipt",
        data=pdf_buffer,
        file_name=f"user{user_id:03d}.pdf",
        mime="application/pdf",
    )


def show_videos_page(eval_id):
    prompt_id, criteria_id, combo_id, turn_id = eval_id


    eval_batch_size = get_eval_batch_size()
    st.subheader(f"{st.session_state.current_index+1}/{eval_batch_size}")
    st.progress(st.session_state.current_index / eval_batch_size)
    st.caption(f"Prompt id: {prompt_id:03d} - Criteria id: {criteria_id}")

    # Initialize counters in session state
    if "clicked_video_count" not in st.session_state:
        st.session_state.clicked_video_count = 0
    if "clicked_video_ids" not in st.session_state:
        st.session_state.clicked_video_ids = set()

    st.markdown(f"#### Criteria - `{CRITERIA[criteria_id][0]}`:")
    st.markdown(f"{CRITERIA[criteria_id][1]}")
    st.caption(f"*Example violation: {CRITERIA[criteria_id][2]}")

    st.divider()

    if CRITERIA[criteria_id][0] in ["Text Following", "Character Emotions"]:
        with open(osp.join(VIDEO_ROOT, MODEL_LIST[0], f"prompt-{prompt_id}/prompt.txt")) as f:
            prompt = f.read()
        st.markdown("#### Prompt:")
        st.markdown(f"{prompt}")
        st.divider()    

    combo = list(get_combo(combo_id))

    rng = random.Random(prompt_id * criteria_id * combo_id * turn_id)
    rng.shuffle(combo)

    left_model = combo[0]
    right_model = combo[1]

    def get_model_path(model_name):
        return osp.join(VIDEO_ROOT, model_name, f"prompt-{prompt_id}/000000.mp4")

    left_video_path = get_model_path(left_model)
    right_video_path = get_model_path(right_model)

    cols = st.columns(2)

    with cols[0]:
        st.markdown("Left")
        st.video(left_video_path, autoplay=False)
    
    with cols[1]:
        st.markdown("Right")
        st.video(right_video_path, autoplay=False)

    rating_mapping = {
        "left": 0,
        "tie": 1,
        "right": 2
    }

    rating = st.pills(f"Which video is better?", options=["left", "tie", "right"], key=f"vid-{prompt_id}-{criteria_id}-{turn_id}-{combo_id}")

    if rating is None:
        st.warning(
            f"‼️ Please choose which video is better. If the videos perform equally for the given criteria, please choose tie."
        )
        return left_model, right_model, None

    return left_model, right_model, rating_mapping[rating]


def admin_page():
    st.title("Admin Page")
    password = st.text_input("Enter admin password:", type="password")
    if password == "lakeside6":
        st.success("Access granted!")

        report_data = io.StringIO()
        entries, col_names = fetch_all_responses()
        json.dump(tuple(col_names), report_data)
        report_data.write("\n")

        for entry in entries:
            json.dump(entry, report_data)
            report_data.write("\n")

        report_data.seek(0)

        st.download_button(
            label="📥 Download Admin Report",
            data=report_data.getvalue(),
            file_name="admin_report.jsonl",
            mime="application/jsonl",
        )
        st.write("Refresh the page before downloading the most recent report.")
    else:
        if password:
            st.error("Access denied! Incorrect password.")
