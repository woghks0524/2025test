import streamlit as st
import gspread
import json
import random
import time
from openai import OpenAI
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import re
seoul_tz = pytz.timezone("Asia/Seoul")

# --- 기본 세팅 ---
st.set_page_config(page_title="(학생용)AI 서술형 평가 도우미", layout="wide")
st.caption("AI 서술형 평가 도우미: 자동채점과 맞춤형 피드백, 4학년")
st.caption("버튼 클릭, 텍스트 입력 등 동작을 요청하고 오른쪽 상단의 RUNNING 아이콘이 사라질 때까지 기다려주세요.")
st.header(":pencil: 서술형 평가 연습하기(학생용)")

api_keys = st.secrets["api"]["keys"]
client = OpenAI(api_key=random.choice(api_keys))

# --- 세션 초기화 ---
defaults = {
    "page": 0,
    "usingthread": client.beta.threads.create().id,
    "settingname": "", "grade": "", "studentclass": "", "studentnumber": "", "studentname": "",
    "answer1": "", "answer2": "", "answer3": "",
    "feedback1": "", "feedback2": "", "feedback3": "",
    "score1": "", "score2": "", "score3": "",
    "assiapi": "", "assiapi2": "", "vectorapi" : "", 
    "openclose": "open", "sheeturl": "", "feedbackinstruction": ""}

for i in range(1, 4):
    defaults[f"question{i}"] = ""
    defaults[f"correctanswer{i}"] = ""
    defaults[f"image{i}"] = ""
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 페이지 전환 함수 ---
def next_page(): st.session_state.page += 1
def prev_page(): st.session_state.page -= 1
def go_home(): st.session_state.page = 0

# --- 단계별 함수 ---
def step1():
    st.subheader("1단계. 평가 코드 입력하기")
    #st.caption("테스트를 위한 평가 코드 예시입니다. 띄어쓰기 없이 다음 중 하나를 입력하세요. 과학1단원 / 과학2단원 / 과학3단원 / 과학4단원")
    code = st.text_input("평가 코드를 입력하세요")

    if st.button("평가 코드 확인"):
        credentials_dict = json.loads(st.secrets["gcp"]["credentials"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets"
        ])
        gc = gspread.authorize(creds)
        sheet = gc.open(st.secrets["google"]["question"]).sheet1
        data = sheet.get_all_records()

        row = next((r for r in data if r.get("settingname") == code), None)
        if row:
            for k, v in row.items():
                st.session_state[k] = v

            if st.session_state.get("assiapi2"):
                st.session_state["assiapi"] = st.session_state["assiapi2"]

                client.beta.assistants.update(
                    assistant_id=st.session_state["assiapi"],
                     tool_resources={"file_search": {"vector_store_ids": [st.session_state["vectorapi"]]}})
                
            st.success("평가를 성공적으로 불러왔습니다.")

        else:
            st.warning("평가 코드를 다시 확인해주세요.")

    st.write("---")
    col1, col2, col3 = st.columns([1, 1, 3])

    with col1:
        st.button("다음 단계", on_click=next_page, disabled=not bool(st.session_state["settingname"]))

    with col2: 
        st.write('')

    with col3: 
        st.write('')

def step2():
    st.subheader("2단계. 학생 기본정보 입력하기")

    # 1. 4개의 열을 생성합니다.
    col1, col2 = st.columns(2)

    # 2. with 구문을 사용해 각 열에 입력창을 하나씩 넣습니다.
    with col1:
        grade = st.text_input("학년", st.session_state["grade"])
        studentnumber = st.text_input("번호", st.session_state["studentnumber"])


    with col2:
        studentclass = st.text_input("반", st.session_state["studentclass"])
        studentname = st.text_input("이름", st.session_state["studentname"])

    if st.button("저장"):
        if not grade.isdigit():
            st.warning("학년은 숫자로 입력해야 합니다.")
        elif not studentclass.isdigit():
            st.warning("반은 숫자로 입력해야 합니다.")
        elif not studentnumber.isdigit():
            st.warning("번호는 숫자로 입력해야 합니다.")
        elif not studentname.strip():
            st.warning("이름을 입력하세요.")
        else:
            st.session_state["grade"] = grade
            st.session_state["studentclass"] = studentclass
            st.session_state["studentnumber"] = studentnumber
            st.session_state["studentname"] = studentname
            st.success("학생 정보가 저장되었습니다.")

    st.write("---")
    col1, col2, col3 = st.columns([1, 1, 3])

    with col1:
        st.button("이전 단계", on_click=prev_page)
    
    with col2:
        st.button("다음 단계", on_click=next_page, disabled=not bool(st.session_state['studentname']))


    with col3: 
        st.write('')

def step3():
    st.subheader("3단계. 답안 작성하기")
    tabs = st.tabs(["1번 문항", "2번 문항", "3번 문항"])

    for i, tab in enumerate(tabs, start=1):
        with tab:
            q = st.session_state[f"question{i}"]
            st.markdown(f"**{q}**")

            img = st.session_state.get(f"image{i}", "")
            if img:
                st.image(img, caption=f"{i}번 문항 이미지", width=300)

            answer = st.text_area(f"{i}번 문항 답안", value=st.session_state[f"answer{i}"], key=f"answer_input_{i}")

            if st.button(f"{i}번 답안 저장"):
                st.session_state[f"answer{i}"] = answer
                st.success(f"{i}번 답안이 저장되었습니다.")


    st.write("---")
    col1, col2, col3 = st.columns([1, 1, 3])

    with col1:
        st.button("이전 단계", on_click=prev_page)
    
    with col2:
        st.button("다음 단계", on_click=next_page) 

    with col3: 
        st.write('')

def step4():
    st.subheader("4단계. 채점 결과 및 피드백 확인하기")
    tabs = st.tabs(["1번 피드백", "2번 피드백", "3번 피드백"])

    def extract_score(text):
        match = re.search(r"(\d+)\s*점", text)
        return int(match.group(1)) if match else None    

    if st.button("채점 결과 및 피드백 확인"):
        st.session_state["openclose"] = "close"
        for i in range(1, 4):
            q = st.session_state[f"question{i}"]
            a = st.session_state[f"answer{i}"]
            instructions = st.session_state["feedbackinstruction"]
            if not a: continue

            client.beta.threads.messages.create(
                thread_id=st.session_state["usingthread"],
                role="user",
                content = f"""
{i}번 문항에 대해 학생의 답안을 채점하고, 
** instructions에 따라 1~5문단 형식으로 피드백을 작성해주세요.
** instructions에 나와 있는 대로 생성합니다. 
instructions에 따르면 채점 결과에 따라 생성하는 피드백의 내용이 달라지므로 꼭 확인하세요. 
문항, 학생이 입력한 답안, 채점 결과(점수+이유), 피드백 내용(점수에 따라 피드백 형식이 달라짐)을 각각 서로 다른 문단으로 나눠서 읽기 쉽게 보여주세요.

평가 주의 사항: {instructions}
문항: {q}
학생 답안: {a}
"""

            )
            run = client.beta.threads.runs.create(
                thread_id=st.session_state["usingthread"],
                assistant_id=st.session_state["assiapi"] or "asst_x2x5kNPZ5zgwj1YV9iY8E7UC",
                temperature=0.01,
                top_p=0.01)
            
            while client.beta.threads.runs.retrieve(run_id=run.id, thread_id=st.session_state["usingthread"]).status != "completed":
                time.sleep(2)

            msg = client.beta.threads.messages.list(st.session_state["usingthread"])
            feedback = msg.data[0].content[0].text.value.strip()
            st.session_state[f"feedback{i}"] = feedback
            st.session_state[f"score{i}"] = extract_score(feedback)

    for i, tab in enumerate(tabs, start=1):
        with tab:
            st.markdown(st.session_state.get(f"feedback{i}", "피드백 없음"))

    st.write("---")
    col1, col2, col3 = st.columns([1, 1, 3])

    with col1:
        st.button("이전 단계", on_click=prev_page)
    
    with col2:
        st.button("다음 단계", on_click=next_page) 

    with col3: 
        st.write('')

def step5():
    st.subheader("5단계. 결과 저장하기")

    def get_partial_feedback(text):
        paragraphs = re.split(r'\n{2,}', text.strip())
        return "\n\n".join(paragraphs[2:]) if len(paragraphs) >= 3 else text

    if st.button("결과 저장"):
        credentials_dict = json.loads(st.secrets["gcp"]["credentials"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets"
        ])
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_url(st.session_state["sheeturl"])
        worksheet = spreadsheet.get_worksheet(0)

        worksheet.append_row([
            datetime.now(seoul_tz).strftime("%Y-%m-%d %H:%M:%S"),
            st.session_state["settingname"],
            st.session_state["grade"],
            st.session_state["studentclass"],
            st.session_state["studentnumber"],
            st.session_state["studentname"],

            st.session_state["question1"],
            st.session_state["score1"],
            st.session_state["answer1"],
            get_partial_feedback(st.session_state["feedback1"]),

            st.session_state["question2"],
            st.session_state["score2"],
            st.session_state["answer2"],
            get_partial_feedback(st.session_state["feedback2"]),

            st.session_state["question3"],
            st.session_state["score3"],
            st.session_state["answer3"],
            get_partial_feedback(st.session_state["feedback3"])
        ])

        st.success("저장 완료!")

    st.write("---")
    col1, col2, col3 = st.columns([1, 1, 3])

    with col1:
        st.button("이전 단계", on_click=prev_page)
    
    with col2:
        st.button("처음 화면으로", on_click=go_home) 

    with col3: 
        st.write('')

# --- 탭 생성 ---
tabs = st.tabs([
    "1️⃣ 평가 코드 입력하기",
    "2️⃣ 학생 기본정보 입력하기",
    "3️⃣ 답안 작성하기",
    "4️⃣ 채점 결과 및 피드백 확인하기",
    "5️⃣ 결과 저장하기"])

# --- 페이지 전환 제어 ---
pages = [step1, step2, step3, step4, step5]
pages[st.session_state["page"]]()