import streamlit as st
import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# --- 1. 페이지 기본 설정 ---
st.set_page_config(page_title="공장 레이아웃 자동 계산기", page_icon="🏭", layout="centered")

# --- 2. 제목 및 설명 ---
st.title("🏭 공장 레이아웃 자동 계산기")
st.write("공장과 장비의 사양을 입력하면 '등 맞댐' 방식의 최대 배치 가능 대수를 계산하고 시각화합니다.")
st.markdown("---")

# --- 3. 사용자 입력 UI 구성 (수정) ---
st.subheader("1. 공장 사양 입력")
col1, col2 = st.columns(2)
with col1:
    factory_width = st.number_input("공장 가로 길이 (m)", min_value=1.0, value=50.0, step=1.0)
with col2:
    factory_length = st.number_input("공장 세로 길이 (m)", min_value=1.0, value=30.0, step=1.0)

st.subheader("2. 장비 사양 입력")
col1, col2 = st.columns(2)
with col1:
    machine_width = st.number_input("장비 가로 길이 (m)", min_value=0.1, value=5.0, step=0.1)
with col2:
    machine_length = st.number_input("장비 세로 길이 (m)", min_value=0.1, value=3.0, step=0.1)

# [변경점 1] 후면 유지보수 공간 입력 UI 복원 및 명칭 변경
st.subheader("3. 공간 사양 입력")
col1, col2, col3 = st.columns(3)
with col1:
    maintenance_side = st.number_input("장비 좌우 간격 (m)", min_value=0.0, value=1.0, step=0.1)
with col2:
    maintenance_rear = st.number_input("후면 유지보수 공간 (m)", min_value=0.0, value=1.0, step=0.1, help="등을 맞댄 장비 사이의 공간입니다.")
with col3:
    aisle_width = st.number_input("작업 통로 폭 (m)", min_value=0.0, value=3.0, step=0.1, help="장비의 앞면과 앞면 사이의 공간입니다.")

placement_orientation = st.selectbox("배치 방향", ("가로 배치", "세로 배치"))
st.markdown("---")

# --- 4. 계산 실행 버튼 ---
if st.button("레이아웃 계산 실행 🚀"):
    # --- 5. 계산 로직 (사용자 로직 완벽 적용) ---

    # 사용자의 1~4번 로직을 코드로 구현
    
    # 1. 배치 방향에 따라 계산에 사용할 가로/세로 값을 재정의
    if placement_orientation == "가로 배치":
        calc_machine_width = machine_width
        calc_machine_length = machine_length
    else: # 세로 배치
        calc_machine_width = machine_length # 값 스왑
        calc_machine_length = machine_width  # 값 스왑

    # 2. 유지보수 공간은 그대로 유지
    # 3. 통로 방향 결정 및 4. 전체 계산
    if placement_orientation == "가로 배치":
        # 가로 배치: Row는 수평, 통로는 수직 방향
        # 한 줄(Row)에 들어가는 장비 수
        machines_per_row = math.floor(factory_width / (calc_machine_width + maintenance_side)) if (calc_machine_width + maintenance_side) > 0 else 0
        # '장비 쌍 + 후면 공간 + 통로' 세트의 총 세로 길이
        set_length = (calc_machine_length * 2) + maintenance_rear + aisle_width
        num_sets = math.floor(factory_length / set_length) if set_length > 0 else 0
    else: # "세로 배치"
        # 세로 배치: Row는 수직(Column), 통로는 수평 방향
        # 한 열(Column)에 들어가는 장비 수
        machines_per_col = math.floor(factory_length / (calc_machine_length + maintenance_side)) if (calc_machine_length + maintenance_side) > 0 else 0
        # '장비 쌍 + 후면 공간 + 통로' 세트의 총 가로 길이
        set_width = (calc_machine_width * 2) + maintenance_rear + aisle_width
        num_sets = math.floor(factory_width / set_width) if set_width > 0 else 0
        machines_per_row = machines_per_col # 이름 통일

    max_machines = machines_per_row * num_sets * 2
    num_aisles = num_sets - 1 if num_sets > 1 else 0

    # --- 6. 결과 표시 ---
    st.subheader("📊 계산 결과")
    # ... (결과 표시 코드는 이전과 동일)
    st.info(f"선택된 배치 방향: **{placement_orientation}**")
    col1, col2 = st.columns(2); col1.metric("✔️ 최대 장비 대수", f"{max_machines} 대"); col2.metric("↔️ 작업 통로 개수", f"{num_aisles} 개")
    st.metric(f"➡️ 한 줄(Row/Column)당 장비 수", f"{machines_per_row} 대")
    st.metric(f"🔄️ 총 장비 쌍(Paired Row/Column) 세트 수", f"{num_sets} 개")

    # --- 7. Matplotlib으로 정밀 레이아웃 그리기 (가로/세로 로직 완벽 분리) ---
    st.subheader("🖼️ 정밀 예상 레이아웃 (CAD 스타일)")
    fig, ax = plt.subplots(figsize=(12, 12 * (factory_length / factory_width)))
    ax.add_patch(patches.Rectangle((0, 0), factory_width, factory_length, lw=2, ec='cyan', fc='black'))

    if placement_orientation == "가로 배치":
        # 가로 배치 그리기 로직 (완성된 상태)
        total_content_width = (machines_per_row * (machine_width + maintenance_side)) - maintenance_side
        total_content_length = (num_sets * ((machine_length * 2) + maintenance_rear + aisle_width)) - aisle_width if num_sets > 1 else num_sets * ((machine_length * 2) + maintenance_rear)
        x_offset = (factory_width - total_content_width) / 2
        y_offset = (factory_length - total_content_length) / 2
        current_y = y_offset
        for i in range(num_sets):
            for j in range(machines_per_row):
                mc_x = x_offset + j * (machine_width + maintenance_side)
                ax.add_patch(patches.Rectangle((mc_x, current_y), machine_width, machine_length, ec='white', fc='darkgray'))
            y_for_second_row = current_y + machine_length + maintenance_rear
            for j in range(machines_per_row):
                mc_x = x_offset + j * (machine_width + maintenance_side)
                ax.add_patch(patches.Rectangle((mc_x, y_for_second_row), machine_width, machine_length, ec='white', fc='darkgray'))
            current_y += (machine_length * 2) + maintenance_rear + aisle_width
    
    else: # "세로 배치"
        # [변경점] 세로 배치 시에는 그릴 때 machine_width와 machine_length를 서로 바꿔서 전달
        total_content_width = (num_sets * ((machine_length * 2) + maintenance_rear + aisle_width)) - aisle_width if num_sets > 1 else num_sets * ((machine_length * 2) + maintenance_rear)
        total_content_length = (machines_per_row * (machine_width + maintenance_side)) - maintenance_side
        x_offset = (factory_width - total_content_width) / 2
        y_offset = (factory_length - total_content_length) / 2
        current_x = x_offset
        for i in range(num_sets):
            # 첫 번째 열 (왼쪽)
            for j in range(machines_per_row):
                mc_y = y_offset + j * (machine_width + maintenance_side)
                ax.add_patch(patches.Rectangle((current_x, mc_y), machine_length, machine_width, ec='white', fc='darkgray')) # <-- 크기 변경
            # 두 번째 열 (오른쪽)
            x_for_second_row = current_x + machine_length + maintenance_rear # <-- 간격 기준 변경
            for j in range(machines_per_row):
                mc_y = y_offset + j * (machine_width + maintenance_side)
                ax.add_patch(patches.Rectangle((x_for_second_row, mc_y), machine_length, machine_width, ec='white', fc='darkgray')) # <-- 크기 변경
            current_x += (machine_length * 2) + maintenance_rear + aisle_width # <-- 간격 기준 변경

    ax.set_xlim(-5, factory_width + 5); ax.set_ylim(-5, factory_length + 5)
    ax.set_aspect('equal', adjustable='box'); ax.set_facecolor('black')
    st.pyplot(fig)