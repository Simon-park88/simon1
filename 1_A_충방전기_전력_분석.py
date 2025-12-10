import streamlit as st
import pandas as pd
import numpy as np
import math
from scipy.interpolate import griddata

# --- 페이지 기본 설정 ---
st.set_page_config(layout="wide")
st.title("⚡ 배터리 레시피 계산기")

# --- 1. st.session_state 초기화 및 콜백 함수 ---
DEFAULT_SPECS = {
    'cell_capacity': 211.10, 'equipment_spec': '60A - 300A', 'control_channels': 16,
    'test_channels': 800, 'standby_power': 1572.0, 'cable_area': 150.0,
    'cable_length': 3.0, 'repetition_count': 1,
    'recipe_to_manage': '선택하세요' # 관리 UI용
}

def initialize_state():
    """세션 상태 초기화"""
    if 'input_df' not in st.session_state: st.session_state.input_df = pd.DataFrame(columns=["모드", "테스트", "전압(V)", "전류(A)", "전력(W)", "시간 제한(H)"])
    if 'result_df' not in st.session_state: st.session_state.result_df = pd.DataFrame()
    if 'saved_recipes' not in st.session_state: st.session_state.saved_recipes = {}
    if 'cp_cccv_details' not in st.session_state: st.session_state.cp_cccv_details = {}
    for key, value in DEFAULT_SPECS.items():
        if key not in st.session_state: st.session_state[key] = value

initialize_state()

def load_recipe_callback():
    """선택한 레시피를 불러오는 콜백 함수"""
    recipe_to_load = st.session_state.recipe_to_manage
    if recipe_to_load != "선택하세요" and recipe_to_load in st.session_state.saved_recipes:
        loaded_data = st.session_state.saved_recipes[recipe_to_load]
        for key, value in loaded_data.items():
            # 저장된 결과값은 불러오지 않음
            if key not in ['recipe_table', 'total_kwh', 'max_peak_power', 'total_hours', 'demand_peak_power', 'recipe_table_with_results']:
                st.session_state[key] = value
        
        # DataFrame과 상세 설정은 별도로 로드
        st.session_state.input_df = pd.DataFrame(loaded_data['recipe_table'])
        # 상세 설정의 key가 문자열로 저장되었을 수 있으므로 int로 변환
        st.session_state.cp_cccv_details = {int(k): v for k, v in loaded_data.get('cp_cccv_details', {}).items()}

        st.success(f"'{recipe_to_load}' 레시피를 성공적으로 불러왔습니다!")

def delete_recipe_callback():
    """선택한 레시피를 삭제하는 콜백 함수"""
    recipe_to_delete = st.session_state.recipe_to_manage
    if recipe_to_delete != "선택하세요" and recipe_to_delete in st.session_state.saved_recipes:
        del st.session_state.saved_recipes[recipe_to_delete]
        st.session_state.recipe_to_manage = "선택하세요"
        st.success(f"'{recipe_to_delete}' 레시피를 삭제했습니다.")
    else:
        st.warning("삭제할 레시피를 먼저 선택해주세요.")


# --- 2. 레시피 관리 UI (다른 페이지와 통일) ---
with st.expander("📂 저장된 레시피 관리", expanded=True):
    if not st.session_state.saved_recipes:
        st.info("저장된 레시피가 없습니다.")
    else:
        col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
        with col1:
            st.selectbox("관리할 레시피를 선택하세요",
                         options=["선택하세요"] + list(st.session_state.saved_recipes.keys()),
                         key="recipe_to_manage")
        with col2:
            st.button("📥 선택 레시피 불러오기", on_click=load_recipe_callback, use_container_width=True)
        with col3:
            st.button("⚠️ 선택 레시피 삭제", on_click=delete_recipe_callback, use_container_width=True)
st.markdown("---")


# --- 3. 효율 데이터 테이블 및 계산 함수 정의 ---
#<editor-fold desc="효율 계산 함수">
COPPER_RESISTIVITY = 1.72e-8
charge_currents = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230, 240, 250, 260, 270, 280, 290, 300])
charge_voltages = np.array([3.3, 4.2, 5.0])
charge_eff_3_3V = np.array([48.62, 63.88, 71.01, 75.43, 78.54, 80.64, 81.90, 82.71, 83.32, 83.78, 84.07, 84.25, 84.25, 84.09, 83.95, 83.75, 83.63, 83.48, 83.33, 83.11, 82.81, 82.49, 82.17, 81.83, 81.51, 81.16, 80.78, 80.38, 79.99, 79.56]) / 100.0
charge_eff_4_2V = np.array([49.46, 64.42, 72.12, 76.76, 79.58, 81.46, 82.81, 83.85, 84.56, 84.90, 85.15, 85.37, 85.44, 85.49, 85.38, 85.25, 85.15, 85.02, 84.89, 84.71, 84.50, 84.28, 83.99, 83.70, 83.40, 83.09, 82.76, 82.42, 82.06, 81.68]) / 100.0
charge_eff_5_0V = np.array([53.24, 67.85, 75.24, 79.30, 81.82, 83.63, 84.88, 85.71, 86.15, 86.55, 86.82, 87.01, 86.99, 86.95, 86.83, 86.75, 86.68, 86.56, 86.36, 86.18, 85.94, 85.73, 85.48, 85.22, 84.94, 84.64, 84.32, 84.00, 83.65, 83.31]) / 100.0
discharge_currents = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230, 240, 250, 260, 270, 280, 290, 300])
discharge_voltages = np.array([3.3, 4.2, 5.0])
discharge_eff_3_3V = np.array([-16.20, 39.95, 56.71, 65.99, 70.81, 74.11, 76.21, 77.63, 78.69, 79.58, 80.14, 80.52, 80.77, 80.78, 80.75, 80.58, 80.47, 79.42, 79.99, 79.68, 79.31, 78.93, 78.55, 78.13, 77.62, 77.10, 76.61, 76.05, 75.40, 74.87]) / 100.0
discharge_eff_4_2V = np.array([-6.35, 45.02, 61.23, 70.32, 74.83, 77.77, 79.81, 81.19, 82.18, 82.85, 83.29, 83.56, 83.63, 83.72, 83.75, 83.70, 83.56, 83.37, 83.16, 82.83, 82.59, 82.28, 81.93, 81.57, 81.17, 80.76, 80.33, 79.83, 79.36, 78.88]) / 100.0
discharge_eff_5_0V = np.array([9.00, 51.99, 65.99, 74.24, 78.26, 80.71, 82.37, 83.62, 84.36, 84.89, 85.24, 85.44, 85.63, 85.71, 85.66, 85.60, 85.46, 85.27, 85.06, 84.83, 84.58, 84.27, 83.99, 83.65, 83.29, 82.92, 82.53, 82.10, 81.66, 81.23]) / 100.0

def structure_data_for_interpolation(currents, voltages, eff_data_list):
    points, values = [], []
    for i, current in enumerate(currents):
        for j, voltage in enumerate(voltages):
            points.append([current, voltage])
            values.append(eff_data_list[j][i])
    return np.array(points), np.array(values)

charge_points, charge_values = structure_data_for_interpolation(charge_currents, charge_voltages, [charge_eff_3_3V, charge_eff_4_2V, charge_eff_5_0V])
discharge_points, discharge_values = structure_data_for_interpolation(discharge_currents, discharge_voltages, [discharge_eff_3_3V, discharge_eff_4_2V, discharge_eff_5_0V])

def calculate_cable_resistance(length_m, area_sqmm):
    if area_sqmm <= 0: return 0
    area_m2 = area_sqmm * 1e-6
    return COPPER_RESISTIVITY * (length_m * 2) / area_m2

def get_efficiency(mode, voltage, current, equipment_spec, cable_length_m, cable_area_sqmm):
    current = abs(current)
    try:
        max_current_str = equipment_spec.split('-')[1].strip().replace('A', '')
        max_current = int(max_current_str)
        scaling_factor = max_current / 300.0
    except (IndexError, ValueError):
        scaling_factor = 1.0
    
    equivalent_current = current / scaling_factor if scaling_factor > 0 else 0
    voltage_clipped = np.clip(voltage, 3.3, 5.0)
    current_clipped = np.clip(equivalent_current, 10, 300)

    if mode == 'Charge': points, values = charge_points, charge_values
    elif mode == 'Discharge': points, values = discharge_points, discharge_values
    else: return 1.0

    eta_table = griddata(points, values, (current_clipped, voltage_clipped), method='linear')
    if np.isnan(eta_table):
        eta_table = griddata(points, values, (current_clipped, voltage_clipped), method='nearest')

    R_3m_150sq = calculate_cable_resistance(3.0, 150.0)
    R_new = calculate_cable_resistance(cable_length_m, cable_area_sqmm)

    eta_adjusted = eta_table
    if voltage > 0 and current > 0 :
        if mode == 'Charge':
            eta_pure = eta_table * (1 + (equivalent_current * R_3m_150sq) / voltage)
            eta_adjusted = eta_pure / (1 + (current * R_new) / voltage)
        else: # Discharge
            denominator = 1 - (equivalent_current * R_3m_150sq) / voltage
            if denominator <= 0: return -1.0
            eta_pure = eta_table / denominator
            eta_adjusted = eta_pure * (1 - (current * R_new) / voltage)
    
    if mode == 'Charge': return np.clip(eta_adjusted, 0, 1.0)
    else: return np.clip(eta_adjusted, -np.inf, 1.0)
#</editor-fold>

# --- 4. 기본 정보 및 장비 사양 입력 ---
st.subheader("기본 정보 입력"); st.number_input("셀 용량 (Ah)", key='cell_capacity', min_value=0.1, step=1.0, format="%.2f"); st.markdown("---")
st.subheader("장비 및 배선 사양 입력")
col1, col2, col3 = st.columns(3)
with col1:
    st.selectbox("장비 사양", options=['2A - 10A', '5A - 25A', '10A - 50A', '20A - 100A', '30A - 150A', '40A - 200A', '60A - 300A', '120A - 600A', '180A - 900A', '240A - 1200A', '300A - 1500A', '360A - 1800A', '420A - 2000A'], key='equipment_spec')
    st.number_input("대기전력 (W)", min_value=0.0, step=1.0, key='standby_power', format="%.2f")
with col2:
    st.number_input("컨트롤 채널 수 (CH)", min_value=1, step=1, key='control_channels')
    st.number_input("테스트 채널 수 (CH)", min_value=1, step=1, key='test_channels')
with col3:
    st.number_input("배선 단면적 (SQ)", min_value=1.0, step=1.0, key='cable_area', format="%.1f")
    st.number_input("배선 길이 (M)", min_value=0.1, step=0.1, key='cable_length', format="%.1f")

required_equipment = math.ceil(st.session_state.test_channels / st.session_state.control_channels) if st.session_state.control_channels > 0 else 0
st.metric(label="✅ 필요 장비 수량 (자동 계산)", value=f"{required_equipment} F"); st.markdown("---")
st.subheader("테스트 옵션"); st.number_input("레시피 반복 횟수", min_value=1, step=1, key='repetition_count'); st.markdown("---")

# --- 5. 레시피 테이블 UI ---
#<editor-fold desc="레시피 테이블 UI">
uploaded_file = st.file_uploader("엑셀 파일로 레시피를 업로드하세요 (A:모드, B:테스트, C:전압, D:전류, E:전력, F:시간)", type=['xlsx', 'xls'])
if uploaded_file is not None:
    try:
        df_from_excel = pd.read_excel(uploaded_file, header=None, names=["모드", "테스트", "전압(V)", "전류(A)", "전력(W)", "시간 제한(H)"])
        st.session_state.input_df = df_from_excel
        st.success("엑셀 파일의 내용으로 레시피를 성공적으로 불러왔습니다!")
    except Exception as e:
        st.error(f"엑셀 파일을 읽는 중 오류가 발생했습니다: {e}")
if st.button("➕ 스텝 추가"):
    new_step = pd.DataFrame([{"모드": "Rest", "테스트": "-", "시간 제한(H)": 1.0}])
    st.session_state.input_df = pd.concat([st.session_state.input_df, new_step], ignore_index=True)
    st.rerun()
st.session_state.input_df['모드'] = st.session_state.input_df['모드'].fillna('Rest')
st.session_state.input_df['테스트'] = st.session_state.input_df['테스트'].fillna('-')
edited_df = st.data_editor(
    st.session_state.input_df,
    column_config={
        "모드": st.column_config.SelectboxColumn("모드", options=["Charge", "Discharge", "Rest"], required=True),
        "테스트": st.column_config.SelectboxColumn("테스트 방식", options=["CC", "CP", "CCCV", "-"], required=True, help="CP모드는 전력(W) 필수, 전압(V)과 전류(A) 중 하나만 입력. CCCV는 아래 상세설정 필수."),
        "전압(V)": st.column_config.NumberColumn("전압 (V)", format="%.2f", help="CCCV모드에서는 CC구간의 평균전압을 입력하세요."),
        "전류(A)": st.column_config.NumberColumn("전류 (A)", format="%.2f", help="CCCV모드에서는 CC구간의 전류를 입력하세요."),
        "전력(W)": st.column_config.NumberColumn("전력 (W)", format="%.2f"),
        "시간 제한(H)": st.column_config.NumberColumn("시간 제한 (H)", format="%.2f"),
    },
    hide_index=True,
    num_rows="dynamic",
)
if len(edited_df) < len(st.session_state.input_df):
    new_indices = set(edited_df.index)
    current_detail_indices = set(st.session_state.cp_cccv_details.keys())
    indices_to_delete = current_detail_indices - new_indices
    if indices_to_delete:
        for idx in indices_to_delete:
            st.session_state.cp_cccv_details.pop(idx, None)
        st.rerun()
st.session_state.input_df = edited_df
#</editor-fold>
# --- 6. 상세 조건 설정 UI ---
#<editor-fold desc="상세 조건 설정 UI">
with st.expander("💡 CP / CCCV 모드 상세 조건 설정 (고급)"):
    detail_steps = {i: row for i, row in edited_df.iterrows() if row['테스트'] in ['CP', 'CCCV']}
    if not detail_steps:
        st.warning("현재 레시피에 상세 설정이 필요한 스텝(CP, CCCV)이 없습니다.")
    else:
        detail_step_options = {i: f"{i+1}번 스텝 ({row['테스트']} / {row['모드']})" for i, row in detail_steps.items()}
        selected_step_index = st.selectbox( "설정할 스텝을 선택하세요", options=list(detail_step_options.keys()), format_func=lambda x: detail_step_options[x])
        if selected_step_index is not None:
            current_details = st.session_state.cp_cccv_details.get(selected_step_index, {})
            selected_step_info = detail_steps[selected_step_index]
            test_type = selected_step_info['테스트']; mode = selected_step_info['모드']
            st.write(f"#### {selected_step_index + 1}번 스텝 ({test_type}) 상세 설정")
            if test_type == 'CP':
                start_v_current = current_details.get('start_v'); end_v_current = current_details.get('end_v')
                default_start_placeholder = "자동 (충전: 2.7V, 방전: 4.2V)"
                col_cp1, col_cp2 = st.columns(2)
                with col_cp1: start_v_input = st.number_input("시작 전압 (V)", value=start_v_current, placeholder=default_start_placeholder, format="%.2f", key=f"start_v_{selected_step_index}")
                with col_cp2: end_v_input = st.number_input("종료(Cut-off) 전압 (V)", value=end_v_current, placeholder="필수 입력", format="%.2f", key=f"end_v_{selected_step_index}")
                start_v_final = start_v_input if (start_v_input is not None and start_v_input > 0) else (2.7 if mode == 'Charge' else 4.2)
                if end_v_input is not None and end_v_input > 0:
                    avg_v_display = (start_v_final + end_v_input) / 2.0
                    st.success(f"✅ 계산에 사용될 평균 전압: **{avg_v_display:.3f} V**")
                else: st.warning("평균 전압을 계산하려면 종료(Cut-off) 전압을 입력해야 합니다.")
                if st.button("💾 CP 설정 저장/업데이트", key=f"save_cp_{selected_step_index}"):
                    st.session_state.cp_cccv_details[selected_step_index] = {'start_v': start_v_input, 'end_v': end_v_input}
                    st.success(f"{selected_step_index + 1}번 스텝의 CP 조건이 저장되었습니다.")
            elif test_type == 'CCCV':
                cv_v_current = current_details.get('cv_v'); cutoff_a_current = current_details.get('cutoff_a'); transition_current = current_details.get('transition', 80.0)
                cv_v_input = st.number_input("CV 목표 전압 (V)", value=cv_v_current, placeholder="예: 4.2", format="%.2f", key=f"cv_v_{selected_step_index}")
                cutoff_a_input = st.number_input("종료(Cut-off) 전류 (A)", value=cutoff_a_current, placeholder="예: 2.5", format="%.2f", key=f"cutoff_a_{selected_step_index}")
                transition_input = st.slider("CC→CV 전환 시점 (전체 충전량의 %)", min_value=1, max_value=99, value=int(transition_current), key=f"transition_{selected_step_index}")
                if st.button("💾 CCCV 설정 저장/업데이트", key=f"save_cccv_{selected_step_index}"):
                    st.session_state.cp_cccv_details[selected_step_index] = {'cv_v': cv_v_input, 'cutoff_a': cutoff_a_input, 'transition': float(transition_input)}
                    st.success(f"{selected_step_index + 1}번 스텝의 CCCV 조건이 저장되었습니다.")
    if st.session_state.cp_cccv_details:
        st.markdown("---"); st.write("**현재 저장된 상세 설정:**")
        valid_details = {k: v for k, v in st.session_state.cp_cccv_details.items() if k < len(edited_df)}
        for idx, details in valid_details.items():
            step_type = edited_df.loc[idx, '테스트']
            if step_type == 'CP': st.write(f"- **{idx+1}번 스텝 (CP):** 시작 {details.get('start_v', '자동')}V, 종료 {details.get('end_v', '미설정')}V")
            elif step_type == 'CCCV': st.write(f"- **{idx+1}번 스텝 (CCCV):** CV {details.get('cv_v')}V, Cut-off {details.get('cutoff_a')}A, 전환 {details.get('transition')}%")
#</editor-fold>
# --- 7. 계산 로직 ---
#<editor-fold desc="계산 로직">
if st.button("⚙️ 레시피 계산 실행"):
    try:
        is_valid = True; error_messages = []
        for index, row in edited_df.iterrows():
            if row['테스트'] == 'CP':
                if not (pd.notna(row['전력(W)']) and row['전력(W)'] > 0): is_valid = False; error_messages.append(f"➡️ {index + 1}번 스텝: CP 모드는 '전력(W)' 값을 필수로 입력해야 합니다.")
                if index not in st.session_state.cp_cccv_details:
                    v_filled = pd.notna(row['전압(V)']) and row['전압(V)'] > 0; c_filled = pd.notna(row['전류(A)']) and row['전류(A)'] > 0
                    if v_filled and c_filled: is_valid = False; error_messages.append(f"➡️ {index+1}번 스텝(CP): 상세 설정이 없으면 '전압'과 '전류' 중 하나만 입력해야 합니다.")
                    if not v_filled and not c_filled: is_valid = False; error_messages.append(f"➡️ {index+1}번 스텝(CP): 상세 설정이 없으면 '전압' 또는 '전류' 중 하나를 입력해야 합니다.")
            elif row['테스트'] == 'CCCV':
                if not (pd.notna(row['전류(A)']) and row['전류(A)'] > 0): is_valid = False; error_messages.append(f"➡️ {index + 1}번 스텝(CCCV): '전류(A)'(CC전류) 값을 필수로 입력해야 합니다.")
                if index not in st.session_state.cp_cccv_details or not st.session_state.cp_cccv_details[index].get('cv_v') or not st.session_state.cp_cccv_details[index].get('cutoff_a'): is_valid = False; error_messages.append(f"➡️ {index + 1}번 스텝(CCCV): 상세 설정에서 'CV 목표 전압'과 '종료 전류'를 반드시 입력해야 합니다.")
        if not is_valid:
            for msg in sorted(list(set(error_messages))): st.error(msg)
            st.stop()

        repetition_count = st.session_state.repetition_count
        input_df_for_calc = pd.concat([edited_df.copy()] * repetition_count, ignore_index=True)
        calculated_df = input_df_for_calc
        calculated_columns = ["C-rate", "실제 테스트 시간(H)", "효율(%)", "전력(kW)", "전력량(kWh)", "누적 충전량(Ah)", "SoC(%)"]
        for col in calculated_columns: calculated_df[col] = 0.0
        current_charge_ah = 0.0; specs = st.session_state; max_capacity_ah = specs.cell_capacity
        for index, row in calculated_df.iterrows():
            original_index = index % len(edited_df); mode = row['모드']; test_type = row['테스트']
            if mode == 'Rest':
                time_limit = row['시간 제한(H)']; actual_time = time_limit if pd.notna(time_limit) else 0.0
                total_power_w = specs.standby_power * required_equipment; total_power_kw = total_power_w / 1000.0
                kwh = total_power_kw * actual_time
                soc_val = (current_charge_ah / max_capacity_ah) * 100 if max_capacity_ah > 0 else 0
                calculated_df.loc[index, ['실제 테스트 시간(H)', '전력(kW)', '전력량(kWh)', '누적 충전량(Ah)', 'SoC(%)']] = [actual_time, total_power_kw, kwh, current_charge_ah, soc_val]
            elif test_type == 'CCCV' and mode == 'Charge':
                details = st.session_state.cp_cccv_details[original_index]
                cc_current = row['전류(A)']; avg_v_cc = row['전압(V)'] if pd.notna(row['전압(V)']) else 3.8
                cv_v = details['cv_v']; cutoff_a = details['cutoff_a']; transition_ratio = details['transition'] / 100.0
                chargeable_ah = max_capacity_ah - current_charge_ah
                ah_for_cc = chargeable_ah * transition_ratio; ah_for_cv = chargeable_ah * (1 - transition_ratio)
                time_cc = ah_for_cc / cc_current if cc_current > 0 else 0
                avg_current_cv = (cc_current + cutoff_a) / 2.0 if cc_current and cutoff_a else 0
                time_cv = ah_for_cv / avg_current_cv if avg_current_cv > 0 else 0
                calculated_full_time = time_cc + time_cv
                time_limit = row['시간 제한(H)']
                actual_time = calculated_full_time
                if pd.notna(time_limit) and time_limit > 0 and time_limit < calculated_full_time: actual_time = time_limit
                time_spent_in_cc, time_spent_in_cv = 0, 0
                if actual_time <= time_cc:
                    time_spent_in_cc = actual_time
                    actual_charge_change = time_spent_in_cc * cc_current
                else:
                    time_spent_in_cc = time_cc; time_spent_in_cv = actual_time - time_cc
                    actual_charge_change = ah_for_cc + (time_spent_in_cv * avg_current_cv)
                eff_cc = get_efficiency(mode, avg_v_cc, cc_current, specs.equipment_spec, specs.cable_length, specs.cable_area)
                p_out_cc = avg_v_cc * cc_current; p_in_cc = p_out_cc / eff_cc if eff_cc > 0 else 0
                eff_cv = get_efficiency(mode, cv_v, avg_current_cv, specs.equipment_spec, specs.cable_length, specs.cable_area)
                p_out_cv = cv_v * avg_current_cv; p_in_cv = p_out_cv / eff_cv if eff_cv > 0 else 0
                total_energy_wh_in = (p_in_cc * time_spent_in_cc) + (p_in_cv * time_spent_in_cv)
                avg_p_in_w = total_energy_wh_in / actual_time if actual_time > 0 else 0
                num_full = specs.test_channels // specs.control_channels; rem_ch = specs.test_channels % specs.control_channels
                p_full_total = num_full * ((avg_p_in_w * specs.control_channels) + specs.standby_power)
                p_partial = (avg_p_in_w * rem_ch) + specs.standby_power if rem_ch > 0 else 0
                total_power_w = p_full_total + p_partial; total_power_kw = total_power_w / 1000.0
                kwh = total_power_kw * actual_time
                current_charge_ah += actual_charge_change
                current_charge_ah = np.clip(current_charge_ah, 0, max_capacity_ah)
                soc_percent = (current_charge_ah / max_capacity_ah) * 100 if max_capacity_ah > 0 else 0
                calculated_df.loc[index, ['실제 테스트 시간(H)', '누적 충전량(Ah)', 'SoC(%)', '전력(kW)', '전력량(kWh)']] = [actual_time, current_charge_ah, soc_percent, total_power_kw, kwh]
            elif mode in ['Charge', 'Discharge']: # CC, CP 처리
                voltage, current, power_w = row['전압(V)'], row['전류(A)'], row['전력(W)']
                if test_type == 'CC': current = abs(row['전류(A)']) if pd.notna(row['전류(A)']) else 0
                elif test_type == 'CP':
                    avg_v = None
                    if original_index in st.session_state.cp_cccv_details:
                        details = st.session_state.cp_cccv_details[original_index]
                        start_v_in = details.get('start_v'); end_v_in = details.get('end_v')
                        start_v = start_v_in if (start_v_in is not None and start_v_in > 0) else (2.7 if mode == 'Charge' else 4.2)
                        if end_v_in is not None and end_v_in > 0: avg_v = (start_v + end_v_in) / 2.0
                        elif start_v_in is not None and start_v_in > 0: avg_v = start_v_in
                    if avg_v is not None and avg_v > 0: voltage = avg_v
                    elif pd.notna(row['전류(A)']) and row['전류(A)'] > 0: current = row['전류(A)']; voltage = abs(power_w / current) if power_w > 0 else 0
                    else: voltage = row['전압(V)']
                    current = abs(power_w / voltage) if power_w > 0 and voltage > 0 else 0
                    calculated_df.loc[index, ['전압(V)', '전류(A)']] = [voltage, current]
                charge_change = 0.0
                if pd.notna(voltage) and pd.notna(current) and current > 0:
                    efficiency = get_efficiency(mode, voltage, current, specs.equipment_spec, specs.cable_length, specs.cable_area)
                    time_limit = row['시간 제한(H)']; c_rate = current / specs.cell_capacity if specs.cell_capacity > 0 else 0
                    c_rate_time = specs.cell_capacity / current if current > 0 else float('inf')
                    if mode == 'Charge': soc_time_limit = (max_capacity_ah - current_charge_ah) / current if current > 0 else float('inf')
                    else: soc_time_limit = current_charge_ah / current if current > 0 else float('inf')
                    possible_times = [soc_time_limit, c_rate_time]
                    if time_limit is not None and time_limit > 0: possible_times.append(time_limit)
                    actual_time = min(possible_times)
                    charge_change = actual_time * current
                    current_charge_ah += charge_change if mode == 'Charge' else -charge_change
                    current_charge_ah = np.clip(current_charge_ah, 0, max_capacity_ah)
                    soc_percent = (current_charge_ah / max_capacity_ah) * 100 if max_capacity_ah > 0 else 0
                    if mode == 'Charge':
                        p_out_w = voltage * current; p_in_w = p_out_w / efficiency if efficiency > 0 else 0
                        num_full = specs.test_channels // specs.control_channels; rem_ch = specs.test_channels % specs.control_channels
                        p_full_total = num_full * ((p_in_w * specs.control_channels) + specs.standby_power)
                        p_partial = (p_in_w * rem_ch) + specs.standby_power if rem_ch > 0 else 0
                        total_power_kw = (p_full_total + p_partial) / 1000.0
                    else: # Discharge
                        p_rec_w = voltage * current * efficiency
                        total_rec_w = p_rec_w * specs.test_channels
                        total_standby_w = specs.standby_power * required_equipment
                        total_power_w = total_standby_w - total_rec_w # 대기전력에서 회수전력 차감
                        total_power_kw = total_power_w / 1000.0
                    kwh = total_power_kw * actual_time
                    calculated_df.loc[index, ['C-rate', '효율(%)', '실제 테스트 시간(H)', '누적 충전량(Ah)', 'SoC(%)', '전력(kW)', '전력량(kWh)']] = [c_rate, efficiency * 100.0, actual_time, current_charge_ah, soc_percent, total_power_kw, kwh]
        st.session_state.result_df = calculated_df
        st.success("레시피 계산이 완료되었습니다!")
    except Exception as e:
        st.error(f"계산 중 오류가 발생했습니다: {e}")
#</editor-fold>
# --- 8. 결과 표시 ---
#<editor-fold desc="결과 표시">
st.markdown("---")
st.subheader("레시피 상세 결과")
if 'result_df' in st.session_state and not st.session_state.result_df.empty:
    num_steps_single_cycle = len(edited_df)
    display_df_table = st.session_state.result_df.head(num_steps_single_cycle)
    if st.session_state.repetition_count > 1:
        st.info(f"결과는 1회 반복 기준으로 표시됩니다. (총 {st.session_state.repetition_count}회 반복 계산됨)")
    columns_to_display = ["모드", "테스트", "전압(V)", "전류(A)", "전력(W)", "실제 테스트 시간(H)", "효율(%)", "전력(kW)", "전력량(kWh)", "누적 충전량(Ah)", "SoC(%)"]
    display_df_selected = display_df_table.reindex(columns=columns_to_display).fillna('-')
    st.dataframe(display_df_selected.rename(index=lambda x: x + 1))
    st.markdown("---")
    st.subheader("최종 결과 요약")
    result_df = st.session_state.result_df
    total_time = result_df['실제 테스트 시간(H)'].sum()
    total_kwh = result_df['전력량(kWh)'].sum()
    col_summary1, col_summary2 = st.columns(2)
    with col_summary1: st.metric("총 테스트 시간 (H)", f"{total_time:.2f}")
    with col_summary2: st.metric("총 전력량 (kWh)", f"{total_kwh:.2f}")
    st.write("") 
    max_peak_power = result_df[result_df['전력(kW)'] >= 0]['전력(kW)'].max()
    if pd.isna(max_peak_power): max_peak_power = 0
    total_charge_time = result_df[result_df['모드'] == 'Charge']['실제 테스트 시간(H)'].sum()
    demand_factor = total_charge_time / total_time if total_time > 0 else 0
    demand_peak_power = max_peak_power * demand_factor
    col_peak1, col_peak2 = st.columns(2)
    with col_peak1: st.metric("최대 피크 전력 (kW)", f"{max_peak_power:.2f}", help="레시피 전체에서 소비 전력이 가장 높은 순간의 값입니다 (회생 전력 제외).")
    with col_peak2: st.metric("수용률 적용 피크 전력 (kW)", f"{demand_peak_power:.2f}", help=f"최대 피크 전력에 수용률({demand_factor:.2%})을 적용한 값입니다. (수용률 = 총 충전 시간 / 총 테스트 시간)")
else:
    st.info("아직 계산된 레시피 데이터가 없습니다.")
#</editor-fold>
# --- 9. 계산 결과 저장 ---
st.markdown("---")
st.subheader("💾 현재 레시피 및 결과 저장하기")
save_name_input = st.text_input("저장할 레시피 이름을 입력하세요", key="cycler_save_name_input")
if st.button("현재 레시피 저장"):
    if save_name_input and not st.session_state.input_df.empty:
        result_df = st.session_state.get('result_df', pd.DataFrame())
        total_kwh = result_df['전력량(kWh)'].sum() if not result_df.empty else 0
        max_peak_power = result_df[result_df['전력(kW)'] >= 0]['전력(kW)'].max() if not result_df.empty else 0
        total_hours = result_df['실제 테스트 시간(H)'].sum() if not result_df.empty else 0
        if pd.isna(max_peak_power): max_peak_power = 0
        
        total_charge_time = result_df[result_df['모드'] == 'Charge']['실제 테스트 시간(H)'].sum()
        demand_factor = total_charge_time / total_hours if total_hours > 0 else 0
        demand_peak_power = max_peak_power * demand_factor

        data_to_save = {
            'recipe_table': st.session_state.input_df.copy().to_dict('records'), # DataFrame은 dict로 변환하여 저장
            'cp_cccv_details': st.session_state.cp_cccv_details.copy(),
            'total_kwh': total_kwh,
            'max_peak_power': max_peak_power,
            'total_hours': total_hours,
            'demand_peak_power': demand_peak_power,
        }
        for key in DEFAULT_SPECS:
            data_to_save[key] = st.session_state[key]
        
        st.session_state.saved_recipes[save_name_input] = data_to_save
        st.success(f"'{save_name_input}' 이름으로 현재 레시피와 계산 결과가 저장되었습니다 ✅")
    elif st.session_state.input_df.empty:
        st.warning("저장할 레시피가 비어있습니다.")
    else:
        st.warning("저장할 레시피 이름을 입력해주세요.")
