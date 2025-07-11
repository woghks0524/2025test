import streamlit as st
import openai
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import random
import json
import firebase_admin
from firebase_admin import storage, credentials
import uuid

# --- API 및 초기 설정 ---
api_keys = st.secrets["api"]["keys"]
selected_api_key = random.choice(api_keys)
client = openai.OpenAI(api_key=selected_api_key)
assistant_id = 'asst_2FrZmOonHQCPO6EhXzQ6u3nr'
new_thread = client.beta.threads.create()

st.set_page_config(page_title="서술형 평가(교사용)", layout="wide")
st.caption("웹 어플리케이션 문의사항은 정재환(서울창일초), woghks0524jjh@gmail.com, 010-3393-0283으로 연락주세요.")
st.header(':memo:서술형 평가 만들기(교사용)')

# --- 세션 초기화 ---
defaults = {
    'settingname': '', 'grade': '', 'subject': '', 'publisher': '',
    'question1': '', 'question2': '', 'question3': '',
    'correctanswer1': '', 'correctanswer2': '', 'correctanswer3': '',
    'image1': '', 'image2': '', 'image3': '',
    'feedbackinstruction': '', 'vectorstoreid': '', 'assiapi': '', 'assiapi2': '',
    'usingthread': new_thread.id
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- firebase 초기화 ---
if not firebase_admin._apps:
    firebase_secret = dict(st.secrets["firebase"])
    cred = credentials.Certificate(firebase_secret)
    firebase_admin.initialize_app(cred, {
        "storageBucket": "openendedquestion-60aee.firebasestorage.app"
    })

# --- firebase 함수 설정 ---
def upload_image_to_firebase(file, filename_prefix="img"):
    bucket = storage.bucket()
    ext = file.name.split(".")[-1]
    unique_name = f"{filename_prefix}_{uuid.uuid4()}.{ext}"
    blob = bucket.blob(unique_name)
    blob.upload_from_file(file, content_type=file.type)
    blob.make_public()
    return blob.public_url

# --- Google Sheets 설정 ---
credentials_dict = json.loads(st.secrets["gcp"]["credentials"])
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"])
gc = gspread.authorize(credentials)
spreadsheet = gc.open(st.secrets["google"]["question"])
worksheet = spreadsheet.sheet1

# --- 함수들 ---
def is_code_duplicate(settingname):
    codes = worksheet.col_values(2)
    return settingname in codes

def step1():
    st.subheader("1단계. 평가 코드 만들기")
    with st.container(border=True):
        settingname = st.text_input("학생들이 평가에 참여할 수 있도록 안내하기 위한 평가 코드를 만들어주세요.")
        if st.button("등록하기"):
            if not settingname or settingname.isdigit():
                st.error("평가 코드에는 문자가 반드시 포함되어야 합니다. 숫자로만 이루어진 평가 코드는 사용할 수 없습니다.")
            elif is_code_duplicate(settingname):
                st.error("이미 존재하는 코드입니다.")
            else:
                st.session_state['settingname'] = settingname
                st.success(f"'{settingname}' 평가 코드가 등록되었습니다.")

def step2():
    st.subheader("2단계. 학년, 과목, 출판사 선택하기")
    
    # 선택 항목 제한
    grade = st.selectbox("학년", ["4학년", "5학년"])
    semester = st.selectbox("학기", ["1학기", "2학기"])
    subject = st.selectbox("과목", ["사회", "과학"])
    publisher = st.selectbox("출판사", ["천재교육", "비상교육", "아이스크림미디어"])
    
    if st.button("선택 저장"):
        # 사용자 선택 저장하기
        st.session_state.update({
            "grade": grade,
            "subject": subject,
            "publisher": publisher
        })

        # 조건에 따라 Assistant 선택하기
        if grade == "4학년" and subject == "사회" and publisher == "비상교육":
            st.session_state['assiapi'] = "asst_x2x5kNPZ5zgwj1YV9iY8E7UC" #교사용
            st.session_state['assiapi2'] = "asst_65Lz4YnySDXpYMAcEvnHsIdS" #학생용 > 시트에 저장
            st.session_state['default_vectorstore_id'] = "vs_6854160fff988191b8501574aa4bc607" 
            
        # if grade == "4학년" and subject == "과학" and publisher == "아이스크림미디어":
        #     st.session_state['assiapi'] = "asst_3F0iurK76Erqbyyg3NxFxYIl" # 교사용
        #     st.session_state['assiapi2'] = "asst_lCIy1fw83OCSwDnY3cWGTy5Z" # 학생용 > 시트에 저장
        #     st.session_state['default_vectorstore_id'] = 'vs_685415a46c8481919f80b6568a9a6135'
            
        if grade == "4학년" and subject == "과학" and publisher == "천재교육":
            st.session_state['assiapi'] = "asst_3F0iurK76Erqbyyg3NxFxYIl" # 교사용
            st.session_state['assiapi2'] = "asst_lCIy1fw83OCSwDnY3cWGTy5Z" # 학생용 > 시트에 저장
            st.session_state['default_vectorstore_id'] = 'vs_686a385a08e48191b39c585677beb24d'

        if grade == "5학년" and subject == "사회" and publisher == "천재교육":
            st.session_state['assiapi'] = "asst_eUL9dRiu88WsBaB91SMIKKWL" # 교사용
            st.session_state['assiapi2'] = "asst_bC4O0pNuoPiZupthVLReYRwD" # 학생용 > 시트에 저장
            st.session_state['default_vectorstore_id'] = "vs_6852f0add000819192ca520c178ed3a8"
            
        st.success("선택이 저장되었습니다.")

def step3():
    st.subheader("3단계. 자료 입력하기")

    # 선택 버튼 (1회 선택 후 고정)
    if 'mode' not in st.session_state:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📁 기존 자료 사용"):
                st.session_state['mode'] = "existing"
        with col2:
            if st.button("🆕 새 파일 업로드하여 평가 생성"):
                st.session_state['mode'] = "new"

    # 사용자가 선택했을 경우 분기 실행
    if 'mode' in st.session_state:

        mode = st.session_state['mode']

        if mode == "existing":
            st.info("✅ 기존 Assistant 및 Vectorstore를 사용합니다.")
            # 벡터스토어 ID 설정 (기본값)
            if st.session_state['vectorstoreid'] == '':
                st.session_state['vectorstoreid'] = st.session_state['default_vectorstore_id']
            # 학생용 Assistant도 기존 값 그대로 사용
            # 아무 작업도 하지 않음

        elif mode == "new":
            st.info("✅ 새 파일을 업로드하여 평가를 생성합니다.")

            # 1. 새 벡터스토어 생성
            new_vectorstore = client.beta.vector_stores.create(name="새 벡터 스토어")
            st.session_state['vectorstoreid'] = new_vectorstore.id

            # 2. 교사용 Assistant 복제
            try:
                base_teacher = client.beta.assistants.retrieve(st.session_state['assiapi'])
                new_teacher = client.beta.assistants.create(
                    name=f"{st.session_state['settingname']}_teacher",
                    instructions=base_teacher.instructions,
                    tools=base_teacher.tools or [],
                    model=base_teacher.model,
                    tool_resources={"file_search": {"vector_store_ids": [new_vectorstore.id]}}
                )
                st.session_state['assiapi'] = new_teacher.id
                st.success("✅ 교사용 Assistant 복제 완료")
            except Exception as e:
                st.error(f"교사용 Assistant 복제 실패: {e}")
                return

            # 3. 학생용 Assistant 복제
            try:
                base_student = client.beta.assistants.retrieve(st.session_state['assiapi2'])
                new_student = client.beta.assistants.create(
                    name=f"{st.session_state['settingname']}_student",
                    instructions=base_student.instructions,
                    tools=base_student.tools or [],
                    model=base_student.model,
                    tool_resources={"file_search": {"vector_store_ids": [new_vectorstore.id]}}
                )
                st.session_state['assiapi2'] = new_student.id
                st.success("✅ 학생용 Assistant 복제 완료")
            except Exception as e:
                st.error(f"학생용 Assistant 복제 실패: {e}")
                return

            # 4. 기존 벡터스토어에서 파일 복사
            try:
                source_files = client.beta.vector_stores.files.list(
                    vector_store_id=st.session_state['default_vectorstore_id']
                )
                if hasattr(source_files, 'data'):
                    for file in source_files.data:
                        client.beta.vector_stores.files.create(
                            vector_store_id=st.session_state['vectorstoreid'],
                            file_id=file.id
                        )
                        time.sleep(1)
                    st.success("📁 기존 파일 복사 완료")
            except Exception as e:
                st.warning(f"파일 복사 중 오류: {e}")

            # 5. 새 자료 업로드
            uploaded_file = st.file_uploader("추가 자료 업로드")
            if uploaded_file and st.button("자료 등록"):
                try:
                    uploaded = client.files.create(file=uploaded_file, purpose="assistants")
                    client.beta.vector_stores.files.create(
                        vector_store_id=st.session_state['vectorstoreid'],
                        file_id=uploaded.id
                    )
                    st.success("📎 자료 등록 완료")
                except Exception as e:
                    st.error(f"자료 등록 실패: {e}")

        # mode가 설정된 이후엔 리셋 버튼 제공
        st.divider()
        if st.button("선택 다시 하기"):
            del st.session_state['mode']

def step4():
    st.subheader("4단계. 평가 문항 입력하기")
    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            q1 = st.text_area("1번 문항")
            q2 = st.text_area("2번 문항")
            q3 = st.text_area("3번 문항")
        with col2:
            a1 = st.text_area("1번 모범답안")
            a2 = st.text_area("2번 모범답안")
            a3 = st.text_area("3번 모범답안")
        with col3: 
            image1 = st.file_uploader("1번 문항 이미지", type=["jpg", "png", "jpeg"])
            image2 = st.file_uploader("2번 문항 이미지", type=["jpg", "png", "jpeg"])
            image3 = st.file_uploader("3번 문항 이미지", type=["jpg", "png", "jpeg"])

        if st.button("문항 등록"):

             # 이미지 업로드 → URL만 추출
            image_url = []
            for idx, image in enumerate([image1, image2, image3], start=1):
                if image:
                    url = upload_image_to_firebase(image, f"q{idx}")
                else:
                    url = ""
                image_url.append(url)

            # 세션 상태에 모두 저장
            st.session_state.update({
                'question1': q1, 'question2': q2, 'question3': q3,
                'correctanswer1': a1, 'correctanswer2': a2, 'correctanswer3': a3,
                'image1' : image_url[0], 'image2' : image_url[1], 'image3' : image_url[2]
            })
            st.success("문항 저장 완료")

def step5():
    st.subheader("5단계. 평가 주의사항 입력하기")
    with st.container(border=True):
        st.write("피드백 말투, 점수 구분, 문단 구성 등 자유롭게 입력하세요.")
        note = st.text_area("평가 주의사항")
        if st.button("주의사항 저장"):
            st.session_state['feedbackinstruction'] = note
            st.success("주의사항 저장 완료")

def step6():
    st.subheader("6단계. 확인 및 저장하기")
    if st.button("평가 내용 확인"):
        client.beta.threads.messages.create(
            thread_id=st.session_state['usingthread'],
            role="user",
            temperature=0.01,
            top_p=0.01,
            content=f"""평가 문항 및 모범답안 등록:
1번 문항: {st.session_state['question1']}
1번 모범답안: {st.session_state['correctanswer1']}
2번 문항: {st.session_state['question2']}
2번 모범답안: {st.session_state['correctanswer2']}
3번 문항: {st.session_state['question3']}
3번 모범답안: {st.session_state['correctanswer3']}

...
- 출처는 【5:12†source】와 같은 참조는 보이지 않도록 합니다. 
- ***[교과서 18쪽]과 같이 참고판 파일과 페이지 수로 나타냅니다.
- 모범답안은 파일에서 직접적으로 확인할 수 없는 경우에도 Assistant의 지식을 바탕으로 생성하되, 파일 내용과 상반되지 않도록 한다.
- 답안이 비워지거나 생략되지 않도록 한다.

""")
        client.beta.threads.messages.create(
            thread_id=st.session_state['usingthread'],
            role="user",
            temperature=0.01,
            top_p=0.01,
            content=f"평가 주의사항: {st.session_state['feedbackinstruction']}")
        client.beta.threads.messages.create(
            thread_id=st.session_state['usingthread'],
            temperature=0.01,
            top_p=0.01,
            role="user",
            content="입력한 평가 정보를 모두 요약해서 보여줘. 파일에서 모범답안이 필요한 경우, 벡터스토어를 사용해서 생성해줘. 1번 문항: ~ 보여주고, 문단 바꿔서 1번 모범 답안: ~ 해서 보여줘.")
        run = client.beta.threads.runs.create(
            thread_id=st.session_state['usingthread'],
            assistant_id=st.session_state['assiapi'])
        
        while True:
            result = client.beta.threads.runs.retrieve(
                thread_id=st.session_state['usingthread'],
                run_id=run.id)
            if result.status == "completed":
                break
            time.sleep(2)

        thread_messages = client.beta.threads.messages.list(st.session_state['usingthread'])
        st.write(thread_messages.data[0].content[0].text.value)

        st.markdown("#### 업로드한 문항 이미지")
        for i in range(1, 4):
            image_key = f'image{i}'
            if image_key in st.session_state and st.session_state[image_key]:
                st.image(st.session_state[image_key], caption=f"{i}번 문항 이미지", width=300)

    if st.button("설정 저장하기"):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        worksheet.append_row([
            now, 
            st.session_state['settingname'],
            st.session_state['question1'], st.session_state['question2'], st.session_state['question3'],
            st.session_state['image1'], st.session_state['image2'], st.session_state['image3'],
            st.session_state['correctanswer1'], st.session_state['correctanswer2'], st.session_state['correctanswer3'],
            st.session_state['feedbackinstruction'],
            st.session_state['assiapi2'],
            st.session_state['vectorstoreid']
        ])
        st.success("설정 저장 완료!")

# --- 탭 레이아웃 구성 ---
progress_texts = [
    "현재 진행 상황: 1단계 - 평가 코드 만들기",
    "현재 진행 상황: 2단계 - 학년, 과목, 출판사 선택하기",
    "현재 진행 상황: 3단계 - 자료 입력하기",
    "현재 진행 상황: 4단계 - 서술형 평가 문항 입력하기",
    "현재 진행 상황: 5단계 - 평가 주의사항 입력하기",
    "현재 진행 상황: 6단계 - 확인 및 저장하기"
]

tabs = st.tabs([
    "1️⃣ 평가 코드 만들기",
    "2️⃣ 학년/과목/출판사 선택하기",
    "3️⃣ 추가 자료 입력하기",
    "4️⃣ 평가 문항 입력하기",
    "5️⃣ 주의사항 입력하기",
    "6️⃣ 확인 및 저장하기"
])

with tabs[0]:
    st.info(progress_texts[0])
    step1()

with tabs[1]:
    st.info(progress_texts[1])
    step2()

with tabs[2]:
    st.info(progress_texts[2])
    step3()

with tabs[3]:
    st.info(progress_texts[3])
    step4()

with tabs[4]:
    st.info(progress_texts[4])
    step5()

with tabs[5]:
    st.info(progress_texts[5])
    step6()