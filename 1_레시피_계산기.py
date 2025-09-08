import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(layout="wide")
st.title("⚡ 배터리 레시피 계산기")

# --- ★★★★★ 레시피 불러오기 UI를 최상단으로 이동 ★★★★★ ---
st.subheader("저장된 레시피 불러오기")

if 'saved_recipes' in st.session_state and st.session_state.saved_recipes:
    col_load1, col_load2 = st.columns([0.8, 0.2])
    with col_load1:
        recipe_to_load = st.selectbox("불러올 레시피를 선택하세요", options=list(st.session_state.saved_recipes.keys()))
    with col_load2:
        st.write("")
        st.write("")
        if st.button("📥 선택한 레시피 불러오기"):
            loaded_data = st.session_state.saved_recipes[recipe_to_load]

            # session_state 값들을 먼저 업데이트
            st.session_state.cell_capacity = loaded_data['cell_capacity']
            st.session_state.equipment_spec = loaded_data['equipment_spec']
            st.session_state.control_channels = loaded_data['control_channels']
            st.session_state.test_channels = loaded_data['test_channels']
            st.session_state.standby_power = loaded_data['standby_power']
            st.session_state.drop_voltage = loaded_data['drop_voltage']
            st.session_state.input_df = loaded_data['recipe_table']

            st.success(f"'{recipe_to_load}' 레시피를 성공적으로 불러왔습니다!")
            # ★★★★★ st.rerun()으로 스크립트를 즉시 재실행 ★★★★★
            st.rerun()
else:
    st.info("저장된 레시피가 없습니다.")
st.markdown("---")

# --- 1. 효율 데이터 테이블 및 계산 함수 정의 ---

# 충전 효율 실측 데이터
charge_currents = np.array([0, 60, 100, 160, 300, 2500])
charge_voltages = np.array([3, 4])
# 표의 % 값을 0~1 사이의 소수점으로 변환
charge_efficiencies = np.array([
    [90.00, 90.00], [72.40, 78.10], [69.50, 75.50], [64.90, 71.20],
    [55.40, 60.80], [50.00, 50.00]
]) / 100.0

# 방전 효율 실측 데이터
discharge_currents = np.array([0, 60, 100, 160, 300, 2500])
discharge_voltages = np.array([3, 4])
discharge_efficiencies = np.array([
    [90.00, 90.00], [65.70, 76.00], [60.90, 68.00], [52.30, 64.30],
    [28.70, 46.40], [20.00, 20.00]
]) / 100.0


def interpolate_2d(x, y, x_points, y_points, z_values):
    """2중 선형 보간법을 수행하는 함수 (버그 수정 버전)"""
    # 입력값이 표의 범위를 벗어날 경우, 가장 가까운 경계값으로 처리
    x = np.clip(x, x_points[0], x_points[-1])
    y = np.clip(y, y_points[0], y_points[-1])

    # 입력값 주변의 네 지점 인덱스 찾기
    x_indices = np.searchsorted(x_points, x, side='right')
    y_indices = np.searchsorted(y_points, y, side='right')

    x_idx = np.clip(x_indices - 1, 0, len(x_points) - 2)
    y_idx = np.clip(y_indices - 1, 0, len(y_points) - 2)

    x1, x2 = x_points[x_idx], x_points[x_idx + 1]
    y1, y2 = y_points[y_idx], y_points[y_idx + 1]

    # 네 지점의 효율 값
    z11 = z_values[y_idx, x_idx]
    z12 = z_values[y_idx, x_idx + 1]
    z21 = z_values[y_idx + 1, x_idx]
    z22 = z_values[y_idx + 1, x_idx + 1]

    # 1단계: x축(전압)에 대해 선형 보간
    fx_y1 = (z11 * (x2 - x) + z12 * (x - x1)) / (x2 - x1)
    fx_y2 = (z21 * (x2 - x) + z22 * (x - x1)) / (x2 - x1)

    # 2단계: y축(전류)에 대해 선형 보간
    result = (fx_y1 * (y2 - y) + fx_y2 * (y - y1)) / (y2 - y1)

    return result


def get_efficiency(mode, voltage, current, equipment_spec):
    """모드와 장비 사양에 따라 적절한 효율을 계산"""
    current = abs(current)

    # 1. 모드에 따라 사용할 기본 테이블 선택
    if mode == 'Charge':
        base_current_axis = charge_currents
        voltages_axis = charge_voltages
        efficiencies_table = charge_efficiencies
    elif mode == 'Discharge':
        base_current_axis = discharge_currents
        voltages_axis = discharge_voltages
        efficiencies_table = discharge_efficiencies
    else:  # Rest 모드
        return 1.0

    # 2. 장비 사양 문자열을 분석하여 배수 결정 (로직 수정)
    try:
        # 예: '120A - 600A' -> ' 600A' -> '600' -> 600
        max_current_str = equipment_spec.split('-')[1].strip().replace('A', '')
        max_current = int(max_current_str)
        scaling_factor = max_current / 300.0
    except (IndexError, ValueError):
        # 문자열 분석에 실패할 경우 기본 배수인 1로 설정
        scaling_factor = 1.0

    # 3. 배수를 적용하여 새로운 전류 축 생성
    current_axis_to_use = np.copy(base_current_axis)
    if scaling_factor > 1.0:
        # 0A와 마지막 값(2500A)을 제외한 중간 값들만 스케일링
        current_axis_to_use[1:-1] = base_current_axis[1:-1] * scaling_factor

    # 4. 최종적으로 결정된 축과 테이블로 보간법 수행
    return interpolate_2d(voltage, current, voltages_axis, current_axis_to_use, efficiencies_table)

# --- 2. 'st.session_state' 초기화 ---
# ... (이전 초기화 코드)
if 'cell_capacity' not in st.session_state:
    st.session_state.cell_capacity = 211.10
if 'equipment_spec' not in st.session_state:
    st.session_state.equipment_spec = '60A - 300A'
if 'control_channels' not in st.session_state:
    st.session_state.control_channels = 16
if 'test_channels' not in st.session_state:
    st.session_state.test_channels = 800
if 'standby_power' not in st.session_state:
    st.session_state.standby_power = 1572.0
if 'drop_voltage' not in st.session_state:
    st.session_state.drop_voltage = 0.50
if 'input_df' not in st.session_state:
    st.session_state.input_df = pd.DataFrame(columns=["모드", "전압(V)", "전류(A)", "시간 제한(H)"])
if 'result_df' not in st.session_state:
    # 결과 데이터프레임에 '누적 충전량'과 'SoC' 열 추가
    st.session_state.result_df = pd.DataFrame(columns=[
        "모드", "전압(V)", "전류(A)", "시간 제한(H)", "C-rate",
        "실제 테스트 시간(H)", "효율(%)", "전력(kW)", "전력량(kWh)",
        "누적 충전량(Ah)", "SoC(%)"
    ])
if 'saved_recipes' not in st.session_state:
    st.session_state.saved_recipes = {}

# --- 3. 기본 정보 및 장비 사양 입력 ---
st.subheader("기본 정보 입력")
st.number_input(
    label="셀 용량 (Ah)을 입력하세요",
    key='cell_capacity',
    min_value=0.1,
    step=1.0,
    format="%.2f",
    help="C-rate 계산의 기준이 되는 셀의 공칭 용량입니다."
)
st.markdown("---")

st.subheader("장비 사양 입력")

col1, col2, col3 = st.columns(3)

with col1:
    # ▼▼▼▼▼ 이 부분을 수정하세요 ▼▼▼▼▼
    st.selectbox("장비 사양", options=[
        '60A - 300A',
        '120A - 600A',
        '180A - 900A',
        '240A - 1200A',
        '300A - 1500A',
        '360A - 1800A',
        '420A - 2000A'
    ], key='equipment_spec')
    help = "테스트 전류에 맞는 사양을 선택해 주세요. 사양에 맞지 않는 전류 계산 시, 효율 계산이 정확하지 않을 수 있습니다."

    st.number_input("대기전력 (W)", min_value=0.0, step=1.0, key='standby_power', format="%.2f")
    st.number_input("Drop전압 (V)", min_value=0.0, max_value=0.99, step=0.01, format="%.2f", key='drop_voltage')

with col2:
    st.number_input("컨트롤 채널 수 (CH)", min_value=1, step=1, key='control_channels')

with col3:
    st.number_input("테스트 채널 수 (CH)", min_value=1, step=1, key='test_channels')

# 필요 장비 수량 자동 계산
if st.session_state.control_channels > 0:
    required_equipment = math.ceil(st.session_state.test_channels / st.session_state.control_channels)
else:
    required_equipment = 0
st.metric(label="✅ 필요 장비 수량 (자동 계산)", value=f"{required_equipment} F")
st.markdown("---")

# --- 4. 레시피 테이블 UI ---
st.subheader("레시피 구성 테이블")

# 엑셀 파일 업로드 UI 추가
uploaded_file = st.file_uploader(
    "엑셀 파일로 레시피를 업로드하세요 (A열: 모드, B열: 전압, C열: 전류, D열: 시간 제한)",
    type=['xlsx', 'xls']  # 엑셀 파일 형식만 허용
)

# 파일이 업로드되었을 때 실행되는 로직
if uploaded_file is not None:
    try:
        # 엑셀 파일을 데이터프레임으로 읽어옴 (헤더 없음)
        df_from_excel = pd.read_excel(uploaded_file, header=None)

        # 읽어온 데이터프레임의 열 이름을 우리 앱의 형식에 맞게 변경
        df_from_excel.columns = ["모드", "전압(V)", "전류(A)", "시간 제한(H)"]

        # 현재 레시피 테이블을 업로드된 내용으로 덮어쓰기
        st.session_state.input_df = df_from_excel
        st.success("엑셀 파일의 내용으로 레시피를 성공적으로 불러왔습니다!")

    except Exception as e:
        st.error(f"엑셀 파일을 읽는 중 오류가 발생했습니다: {e}")

if st.button("➕ 스텝 추가"):
    new_step = pd.DataFrame([{"모드": "Rest", "전압(V)": None, "전류(A)": None, "시간 제한(H)": 1.0}])
    st.session_state.input_df = pd.concat([st.session_state.input_df, new_step], ignore_index=True)

# data_editor는 이제 'input_df'를 사용
edited_df = st.data_editor(
    st.session_state.input_df,
    column_config={
        "모드": st.column_config.SelectboxColumn("모드 선택", options=["Charge", "Discharge", "Rest"], required=True),
        "전압(V)": st.column_config.NumberColumn("전압 (V)", format="%.2f"),
        "전류(A)": st.column_config.NumberColumn("전류 (A)", format="%.2f"),
        "시간 제한(H)": st.column_config.NumberColumn("시간 제한 (H)", format="%.2f"),
    },
    hide_index=True,
    num_rows="dynamic",
)
# 사용자가 편집한 내용을 다시 input_df에 저장
st.session_state.input_df = edited_df


# --- 5. 자동 계산 로직 ---

# UI를 깔끔하게 배치하기 위해 컬럼 사용
col1, col2, col3 = st.columns([0.4, 0.2, 0.4])

with col1:
    # '반복 테스트' 토글 스위치 추가
    run_repetition = st.toggle('반복 테스트', help="이 옵션을 켜면 아래 횟수만큼 레시피 전체를 반복하여 계산합니다.")

with col2:
    # 토글이 켜졌을 때만 횟수 입력창 표시
    if run_repetition:
        repetition_count = st.number_input('반복 횟수', min_value=1, step=1, value=1, label_visibility="collapsed")

# 계산 실행 버튼
if st.button("⚙️ 레시피 계산 실행"):
    try:
        # 1. 반복 여부 확인 및 원본 데이터 준비
        input_df_for_calc = st.session_state.input_df.copy()
        if run_repetition and repetition_count > 1:
            st.info(f"{repetition_count}회 반복하여 계산합니다.")
            # 데이터프레임을 지정된 횟수만큼 복제하여 합침
            input_df_for_calc = pd.concat([st.session_state.input_df] * repetition_count, ignore_index=True)

        # 2. 계산을 위한 준비 (이전과 동일)
        calculated_df = input_df_for_calc
        calculated_columns = ["C-rate", "실제 테스트 시간(H)", "효율(%)", "전력(kW)", "전력량(kWh)"]
        for col in calculated_columns:
            calculated_df[col] = 0.0
        # ★★★★★ SoC 트래킹을 위한 변수 초기화 ★★★★★
        # 현재 충전된 용량 (Ah), 0%에서 시작한다고 가정
        current_charge_ah = 0.0
        # 셀의 최대 용량
        max_capacity_ah = st.session_state.cell_capacity
        # 최종 계산을 위한 변수 가져오기

        cell_capacity = st.session_state.cell_capacity
        equipment_spec = st.session_state.equipment_spec
        voltage_drop_value = st.session_state.drop_voltage
        control_channels = st.session_state.control_channels
        standby_power = st.session_state.standby_power
        test_channels = st.session_state.test_channels
        required_equipment = math.ceil(test_channels / control_channels) if control_channels > 0 else 0

        # 각 행을 순회하며 모든 값 재계산
        for index, row in calculated_df.iterrows():
            mode = row['모드']

            # 1. Rest 모드를 먼저 처리
            if mode == 'Rest':
                time_limit = row['시간 제한(H)']

                # Rest는 사용자가 입력한 시간 제한을 그대로 실제 시간으로 사용
                actual_time = time_limit if pd.notna(time_limit) else 0.0

                # Rest 시의 전력은 대기전력만 계산
                total_power_w = standby_power * required_equipment
                total_power_kw = total_power_w / 1000.0
                kwh = total_power_kw * actual_time

                # 계산된 값 업데이트
                calculated_df.at[index, '실제 테스트 시간(H)'] = actual_time
                calculated_df.at[index, '전력(kW)'] = total_power_kw
                calculated_df.at[index, '전력량(kWh)'] = kwh
                # Rest 모드이므로 나머지 계산값은 0으로 설정
                calculated_df.at[index, 'C-rate'] = 0.0
                calculated_df.at[index, '효율(%)'] = 0.0

            # 2. Charge 또는 Discharge 모드이면서, 전압/전류 값이 모두 있을 때만 계산
            elif mode in ['Charge', 'Discharge'] and pd.notna(row['전압(V)']) and pd.notna(row['전류(A)']):
                voltage = row['전압(V)']
                current = abs(row['전류(A)'])
                time_limit = row['시간 제한(H)']

                # 1. C-rate 계산
                c_rate = 0.0
                if cell_capacity > 0 and mode != 'Rest':
                    c_rate = current / cell_capacity
                calculated_df.at[index, 'C-rate'] = c_rate

                # 2. 효율 계산
                efficiency = get_efficiency(mode, voltage, current, equipment_spec)
                calculated_df.at[index, '효율(%)'] = efficiency * 100.0

                # 3. ★★★★★ SoC를 고려한 실제 테스트 시간 계산 ★★★★★
                actual_time = 0.0
                if current > 0:
                    # C-rate 기준 시간 (이론상 최대 시간)
                    c_rate_time = max_capacity_ah / current

                    if mode == 'Charge':
                        # 충전 가능 용량(Ah) = 최대 용량 - 현재 충전량
                        chargeable_ah = max_capacity_ah - current_charge_ah
                        # 충전 가능 시간 = 충전 가능 용량 / 전류
                        soc_time_limit = chargeable_ah / current if current > 0 else float('inf')

                    elif mode == 'Discharge':
                        # 방전 가능 용량(Ah) = 현재 충전량
                        dischargeable_ah = current_charge_ah
                        # 방전 가능 시간 = 방전 가능 용량 / 전류
                        soc_time_limit = dischargeable_ah / current if current > 0 else float('inf')

                    # 1. SoC 기준 시간, 2. C-rate 기준 시간, 3. 사용자 시간 제한 중 가장 짧은 시간 선택
                    possible_times = [soc_time_limit, c_rate_time]
                    if time_limit is not None and time_limit > 0:
                        possible_times.append(time_limit)

                    actual_time = min(possible_times)

                calculated_df.at[index, '실제 테스트 시간(H)'] = actual_time

                # ★★★★★ 현재 충전량 및 SoC 업데이트 ★★★★★
                charge_change = actual_time * current
                if mode == 'Charge':
                    current_charge_ah += charge_change
                elif mode == 'Discharge':
                    current_charge_ah -= charge_change

                # 충전량이 0 미만 또는 최대 용량을 초과하지 않도록 보정
                current_charge_ah = np.clip(current_charge_ah, 0, max_capacity_ah)

                # 계산된 누적 충전량과 SoC(%)를 해당 행에 저장
                calculated_df.at[index, '누적 충전량(Ah)'] = current_charge_ah
                soc_percent = (current_charge_ah / max_capacity_ah) * 100 if max_capacity_ah > 0 else 0
                calculated_df.at[index, 'SoC(%)'] = soc_percent

                # 4. 전력(kW) 계산
                total_power_kw = 0.0
                if mode == 'Charge':
                    power_per_channel_w = ((
                                                       voltage + voltage_drop_value) * current) / efficiency if efficiency > 0 else 0
                    if control_channels > 0:
                        num_full_equip = test_channels // control_channels
                        remaining_channels = test_channels % control_channels
                        power_full_equip_total = num_full_equip * (
                                    (power_per_channel_w * control_channels) + standby_power)
                        power_partial_equip = 0.0
                        if remaining_channels > 0:
                            power_partial_equip = (power_per_channel_w * remaining_channels) + standby_power
                        total_power_w = power_full_equip_total + power_partial_equip
                    total_power_kw = total_power_w / 1000.0
                elif mode == 'Discharge':
                    power_recovered_per_channel_w = (voltage - voltage_drop_value) * current * efficiency
                    total_recovered_power_w = power_recovered_per_channel_w * test_channels
                    total_standby_power_w = standby_power * required_equipment
                    total_power_w = total_standby_power_w - total_recovered_power_w
                    total_power_kw = total_power_w / 1000.0
                elif mode == 'Rest':
                    total_power_w = standby_power * required_equipment
                    total_power_kw = total_power_w / 1000.0
                calculated_df.at[index, '전력(kW)'] = total_power_kw

                # 5. 전력량(kWh) 계산
                kwh = total_power_kw * actual_time
                calculated_df.at[index, '전력량(kWh)'] = kwh

        # 계산이 완료된 테이블을 result_df에 저장
        st.session_state.result_df = calculated_df
        st.success("레시피 계산이 완료되었습니다!")

    except Exception as e:
        st.error(f"계산 중 오류가 발생했습니다: {e}")

# --- 6. 현재 데이터 확인 ---
st.markdown("---")
st.subheader("레시피 상세 결과 (1회차 기준)")

# session_state에 result_df가 있고 비어있지 않은지 먼저 확인
if 'result_df' in st.session_state and not st.session_state.result_df.empty:

    # 1. 화면에 표시할 테이블 데이터 준비
    # 최종 결과 테이블에서 보여줄 열 목록을 직접 선택
    columns_to_display = [
        "모드", "전압(V)", "전류(A)", "실제 테스트 시간(H)", "효율(%)",
        "전력(kW)", "전력량(kWh)", "누적 충전량(Ah)", "SoC(%)"
    ]
    # 전체 결과 중 원본 레시피 길이만큼만 잘라냄
    display_df_full = st.session_state.result_df.head(len(st.session_state.input_df))
    # 그 중에서도 보여주기로 선택한 열만 최종 선택
    display_df_selected = display_df_full[columns_to_display]

    # 최종 테이블 표시
    st.dataframe(display_df_selected.rename(index=lambda x: x + 1))

    # 2. 총합 계산 및 표시 (전체 데이터를 기준으로 수행)
    st.markdown("---")
    st.subheader("최종 결과 요약")

    total_time = st.session_state.result_df['실제 테스트 시간(H)'].sum()
    total_kwh = st.session_state.result_df['전력량(kWh)'].sum()

    col_summary1, col_summary2 = st.columns(2)
    with col_summary1:
        st.metric("총 테스트 시간 (H)", f"{total_time:.2f}")
    with col_summary2:
        st.metric("총 전력량 (kWh)", f"{total_kwh:.2f}")
else:
    st.info("아직 계산된 레시피 데이터가 없습니다.")

# --- 7. 계산 결과 저장 ---
# --- 계산 결과 저장 UI (수정) ---
st.markdown("---")
st.subheader("계산 결과 저장하기")

save_name = st.text_input("저장할 레시피 이름을 입력하세요 (예: 저장레시피 1)")

if st.button("💾 현재 레시피 저장"):
    if save_name and not st.session_state.input_df.empty:
        # 저장할 데이터 구조를 딕셔너리로 변경
        data_to_save = {
            'recipe_table': st.session_state.input_df.copy(), # 수정 가능한 입력 테이블 저장
            'cell_capacity': st.session_state.cell_capacity,
            'equipment_spec': st.session_state.equipment_spec,
            'control_channels': st.session_state.control_channels,
            'test_channels': st.session_state.test_channels,
            'standby_power': st.session_state.standby_power,
            'drop_voltage': st.session_state.drop_voltage
        }
        st.session_state.saved_recipes[save_name] = data_to_save
        st.success(f"'{save_name}' 이름으로 현재 모든 설정이 저장되었습니다!")

    elif st.session_state.result_df.empty:
        st.warning("저장할 계산 결과가 없습니다. 먼저 레시피를 계산해주세요.")
    else:
        st.warning("저장할 레시피 이름을 입력해주세요.")

# 현재 저장된 레시피 목록 보여주기
if 'saved_recipes' in st.session_state and st.session_state.saved_recipes:
    st.markdown("---")
    st.subheader("현재 저장된 레시피 목록")
    st.write(list(st.session_state.saved_recipes.keys()))
    if st.button("⚠️ 저장된 모든 레시피 삭제"):
        st.session_state.saved_recipes = {}
        st.rerun()  # 화면 새로고침