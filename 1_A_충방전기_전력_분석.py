import streamlit as st
import pandas as pd
import numpy as np
import math
from scipy.interpolate import griddata

# --- 페이지 기본 설정 ---
st.set_page_config(layout="wide")
st.title("⚡ 배터리 레시피 계산기")

# --- 레시피 불러오기 UI (최상단) ---
st.subheader("저장된 레시피 불러오기")

if 'saved_recipes' in st.session_state and st.session_state.saved_recipes:
    col_load1, col_load2 = st.columns([0.8, 0.2])
    with col_load1:
        recipe_keys = list(st.session_state.saved_recipes.keys())
        recipe_to_load = st.selectbox("불러올 레시피를 선택하세요", options=recipe_keys)
    with col_load2:
        st.write("")
        st.write("")
        if st.button("📥 선택한 레시피 불러오기"):
            if recipe_to_load:
                loaded_data = st.session_state.saved_recipes[recipe_to_load]
                for key, value in loaded_data.items():
                    if key != 'recipe_table':
                        st.session_state[key] = value
                st.session_state.input_df = loaded_data['recipe_table']
                st.success(f"'{recipe_to_load}' 레시피를 성공적으로 불러왔습니다!")
                st.rerun()
else:
    st.info("저장된 레시피가 없습니다.")
st.markdown("---")


# --- 1. 효율 데이터 테이블 및 계산 함수 정의 ---

# == 물리 상수 ==
COPPER_RESISTIVITY = 1.72e-8

# == (기준 모델) 300A 장비 충전 데이터 ==
charge_currents = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230, 240, 250, 260, 270, 280, 290, 300])
charge_voltages = np.array([3.3, 4.2, 5.0])
charge_eff_3_3V = np.array([48.62, 63.88, 71.01, 75.43, 78.54, 80.64, 81.90, 82.71, 83.32, 83.78, 84.07, 84.25, 84.25, 84.09, 83.95, 83.75, 83.63, 83.48, 83.33, 83.11, 82.81, 82.49, 82.17, 81.83, 81.51, 81.16, 80.78, 80.38, 79.99, 79.56]) / 100.0
charge_eff_4_2V = np.array([49.46, 64.42, 72.12, 76.76, 79.58, 81.46, 82.81, 83.85, 84.56, 84.90, 85.15, 85.37, 85.44, 85.49, 85.38, 85.25, 85.15, 85.02, 84.89, 84.71, 84.50, 84.28, 83.99, 83.70, 83.40, 83.09, 82.76, 82.42, 82.06, 81.68]) / 100.0
charge_eff_5_0V = np.array([53.24, 67.85, 75.24, 79.30, 81.82, 83.63, 84.88, 85.71, 86.15, 86.55, 86.82, 87.01, 86.99, 86.95, 86.83, 86.75, 86.68, 86.56, 86.36, 86.18, 85.94, 85.73, 85.48, 85.22, 84.94, 84.64, 84.32, 84.00, 83.65, 83.31]) / 100.0

# == (기준 모델) 300A 장비 방전 데이터 ==
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

    if mode == 'Charge':
        points, values = charge_points, charge_values
    elif mode == 'Discharge':
        points, values = discharge_points, discharge_values
    else:
        return 1.0

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
        else:
            denominator = 1 - (equivalent_current * R_3m_150sq) / voltage
            if denominator <= 0: return 0
            eta_pure = eta_table / denominator
            eta_adjusted = eta_pure * (1 - (current * R_new) / voltage)
    return np.clip(eta_adjusted, 0, 1.0)

# --- 2. 'st.session_state' 초기화 ---
defaults = {
    'cell_capacity': 211.10,
    'equipment_spec': '60A - 300A',
    'control_channels': 16,
    'test_channels': 800,
    'standby_power': 1572.0,
    'cable_area': 150.0,
    'cable_length': 3.0,
    'repetition_count': 1,
    'input_df': pd.DataFrame(columns=["모드", "테스트", "전압(V)", "전류(A)", "전력(W)", "시간 제한(H)"]),
    'result_df': pd.DataFrame(),
    'saved_recipes': {}
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- 3. 기본 정보 및 장비 사양 입력 ---
st.subheader("기본 정보 입력")
st.number_input("셀 용량 (Ah)", key='cell_capacity', min_value=0.1, step=1.0, format="%.2f")
st.markdown("---")

st.subheader("장비 및 배선 사양 입력")
col1, col2, col3 = st.columns(3)
with col1:
    st.selectbox("장비 사양",
        options=['60A - 300A', '120A - 600A', '180A - 900A', '240A - 1200A', '300A - 1500A', '360A - 1800A', '420A - 2000A'],
        key='equipment_spec',
        help="선택한 사양의 최대 전류를 기준으로 300A 효율표를 스케일링하여 효율을 예측합니다."
    )
    st.number_input("대기전력 (W)", min_value=0.0, step=1.0, key='standby_power', format="%.2f")
with col2:
    st.number_input("컨트롤 채널 수 (CH)", min_value=1, step=1, key='control_channels')
    st.number_input("테스트 채널 수 (CH)", min_value=1, step=1, key='test_channels')
with col3:
    st.number_input("배선 단면적 (SQ)", min_value=1.0, step=1.0, key='cable_area', format="%.1f")
    st.number_input("배선 길이 (M)", min_value=0.1, step=0.1, key='cable_length', format="%.1f")

if st.session_state.control_channels > 0:
    required_equipment = math.ceil(st.session_state.test_channels / st.session_state.control_channels)
else:
    required_equipment = 0
st.metric(label="✅ 필요 장비 수량 (자동 계산)", value=f"{required_equipment} F")
st.markdown("---")

st.subheader("테스트 옵션")
st.number_input("레시피 반복 횟수", min_value=1, step=1, key='repetition_count', help="입력된 레시피 전체를 지정된 횟수만큼 반복하여 계산합니다.")
st.markdown("---")


# --- 4. 레시피 테이블 UI ---
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
        "테스트": st.column_config.SelectboxColumn("테스트 방식", options=["CC", "CP", "-"], required=True),
        "전압(V)": st.column_config.NumberColumn("전압 (V)", format="%.2f"),
        "전류(A)": st.column_config.NumberColumn("전류 (A)", format="%.2f"),
        "전력(W)": st.column_config.NumberColumn("전력 (W)", format="%.2f"),
        "시간 제한(H)": st.column_config.NumberColumn("시간 제한 (H)", format="%.2f"),
    },
    hide_index=True,
    num_rows="dynamic",
)
st.session_state.input_df = edited_df

# --- 5. 계산 로직 ---
if st.button("⚙️ 레시피 계산 실행"):
    try:
        repetition_count = st.session_state.repetition_count
        if not st.session_state.input_df.empty:
            input_df_for_calc = pd.concat([st.session_state.input_df.copy()] * repetition_count, ignore_index=True)
        else:
            input_df_for_calc = st.session_state.input_df.copy()

        calculated_df = input_df_for_calc
        calculated_columns = ["C-rate", "실제 테스트 시간(H)", "효율(%)", "전력(kW)", "전력량(kWh)", "누적 충전량(Ah)", "SoC(%)"]
        for col in calculated_columns:
            calculated_df[col] = 0.0
        
        current_charge_ah = 0.0
        specs = st.session_state
        max_capacity_ah = specs.cell_capacity
        
        for index, row in calculated_df.iterrows():
            mode = row['모드']
            test_type = row['테스트']
            
            if mode == 'Rest':
                time_limit = row['시간 제한(H)']
                actual_time = time_limit if pd.notna(time_limit) else 0.0
                total_power_w = specs.standby_power * required_equipment
                total_power_kw = total_power_w / 1000.0
                kwh = total_power_kw * actual_time
                calculated_df.at[index, '실제 테스트 시간(H)'] = actual_time
                calculated_df.at[index, '전력(kW)'] = total_power_kw
                calculated_df.at[index, '전력량(kWh)'] = kwh
                calculated_df.at[index, '누적 충전량(Ah)'] = current_charge_ah
                soc_percent = (current_charge_ah / max_capacity_ah) * 100 if max_capacity_ah > 0 else 0
                calculated_df.at[index, 'SoC(%)'] = soc_percent

            elif mode in ['Charge', 'Discharge']:
                voltage = row['전압(V)']
                current = 0.0
                
                if test_type == 'CC' and pd.notna(row['전류(A)']):
                    current = abs(row['전류(A)'])
                elif test_type == 'CP' and pd.notna(row['전력(W)']) and pd.notna(voltage) and voltage > 0:
                    power_w = row['전력(W)']
                    current = abs(power_w / voltage)

                if pd.notna(voltage) and current > 0:
                    efficiency = get_efficiency(mode, voltage, current, specs.equipment_spec, specs.cable_length, specs.cable_area)
                    
                    time_limit = row['시간 제한(H)']
                    c_rate = current / specs.cell_capacity if specs.cell_capacity > 0 else 0
                    
                    c_rate_time = specs.cell_capacity / current if current > 0 else float('inf')
                    if mode == 'Charge':
                        chargeable_ah = max_capacity_ah - current_charge_ah
                        soc_time_limit = chargeable_ah / current if current > 0 else float('inf')
                    else:
                        dischargeable_ah = current_charge_ah
                        soc_time_limit = dischargeable_ah / current if current > 0 else float('inf')
                    
                    possible_times = [soc_time_limit, c_rate_time]
                    if time_limit is not None and time_limit > 0:
                        possible_times.append(time_limit)
                    actual_time = min(possible_times)
                    
                    charge_change = actual_time * current
                    if mode == 'Charge':
                        current_charge_ah += charge_change
                    elif mode == 'Discharge':
                        current_charge_ah -= charge_change
                    current_charge_ah = np.clip(current_charge_ah, 0, max_capacity_ah)
                    soc_percent = (current_charge_ah / max_capacity_ah) * 100 if max_capacity_ah > 0 else 0

                    total_power_kw = 0.0
                    if mode == 'Charge':
                        power_out_per_channel_w = voltage * current
                        power_in_per_channel_w = power_out_per_channel_w / efficiency if efficiency > 0 else 0
                        if specs.control_channels > 0:
                            num_full_equip = specs.test_channels // specs.control_channels
                            remaining_channels = specs.test_channels % specs.control_channels
                            power_full_equip_total = num_full_equip * ((power_in_per_channel_w * specs.control_channels) + specs.standby_power)
                            power_partial_equip = (power_in_per_channel_w * remaining_channels) + specs.standby_power if remaining_channels > 0 else 0
                            total_power_w = power_full_equip_total + power_partial_equip
                        total_power_kw = total_power_w / 1000.0
                    elif mode == 'Discharge':
                        power_recovered_per_channel_w = voltage * current * efficiency
                        total_recovered_power_w = power_recovered_per_channel_w * specs.test_channels
                        total_standby_power_w = specs.standby_power * required_equipment
                        total_power_w = total_standby_power_w - total_recovered_power_w
                        total_power_kw = total_power_w / 1000.0
                    
                    kwh = total_power_kw * actual_time
                    
                    calculated_df.at[index, 'C-rate'] = c_rate
                    calculated_df.at[index, '효율(%)'] = efficiency * 100.0
                    calculated_df.at[index, '실제 테스트 시간(H)'] = actual_time
                    calculated_df.at[index, '누적 충전량(Ah)'] = current_charge_ah
                    calculated_df.at[index, 'SoC(%)'] = soc_percent
                    calculated_df.at[index, '전력(kW)'] = total_power_kw
                    calculated_df.at[index, '전력량(kWh)'] = kwh
                    
        st.session_state.result_df = calculated_df
        st.success("레시피 계산이 완료되었습니다!")

    except Exception as e:
        st.error(f"계산 중 오류가 발생했습니다: {e}")

# --- 6. 결과 표시 ---
st.markdown("---")
st.subheader("레시피 상세 결과")
if 'result_df' in st.session_state and not st.session_state.result_df.empty:
    columns_to_display = ["모드", "전압(V)", "전류(A)", "실제 테스트 시간(H)", "효율(%)", "전력(kW)", "전력량(kWh)", "누적 충전량(Ah)", "SoC(%)"]
    
    display_df_full = st.session_state.result_df
    display_df_selected = display_df_full[columns_to_display]
    st.dataframe(display_df_selected.rename(index=lambda x: x + 1))

    st.markdown("---")
    st.subheader("최종 결과 요약")
    
    result_df = st.session_state.result_df
    total_time = result_df['실제 테스트 시간(H)'].sum()
    total_kwh = result_df['전력량(kWh)'].sum()
    
    col_summary1, col_summary2 = st.columns(2)
    with col_summary1:
        st.metric("총 테스트 시간 (H)", f"{total_time:.2f}")
    with col_summary2:
        st.metric("총 전력량 (kWh)", f"{total_kwh:.2f}")

    # ★★★★★ 피크 전력 계산 및 표시 로직 추가 ★★★★★
    st.write("") # 여백 추가
    
    # 1. 최대 피크 전력 (Maximum Peak Power)
    # 방전 시 회생 전력(음수값)은 제외하고 최대 소비 전력을 찾음
    max_peak_power = result_df[result_df['전력(kW)'] >= 0]['전력(kW)'].max()
    if pd.isna(max_peak_power):
        max_peak_power = 0

    # 2. 수용률 (Demand Factor) 계산
    # 충전 모드의 시간만 합산
    total_charge_time = result_df[result_df['모드'] == 'Charge']['실제 테스트 시간(H)'].sum()
    if total_time > 0:
        demand_factor = total_charge_time / total_time
    else:
        demand_factor = 0
    
    # 3. 수용률 적용 피크 전력
    demand_peak_power = max_peak_power * demand_factor

    col_peak1, col_peak2 = st.columns(2)
    with col_peak1:
        st.metric("최대 피크 전력 (kW)", f"{max_peak_power:.2f}", 
                  help="레시피 전체에서 소비 전력이 가장 높은 순간의 값입니다 (회생 전력 제외).")
    with col_peak2:
        st.metric("수용률 적용 피크 전력 (kW)", f"{demand_peak_power:.2f}", 
                  help=f"최대 피크 전력에 수용률({demand_factor:.2%})을 적용한 값입니다. (수용률 = 총 충전 시간 / 총 테스트 시간)")

else:
    st.info("아직 계산된 레시피 데이터가 없습니다.")

# --- 7. 계산 결과 저장 ---
st.markdown("---")
st.subheader("계산 결과 저장하기")
save_name = st.text_input("저장할 레시피 이름을 입력하세요 (예: 저장레시피 1)")
if st.button("💾 현재 레시피 저장"):
    if save_name and not st.session_state.input_df.empty:
        data_to_save = {
            'recipe_table': st.session_state.input_df.copy(),
            'cell_capacity': st.session_state.cell_capacity,
            'equipment_spec': st.session_state.equipment_spec,
            'control_channels': st.session_state.control_channels,
            'test_channels': st.session_state.test_channels,
            'standby_power': st.session_state.standby_power,
            'cable_area': st.session_state.cable_area,
            'cable_length': st.session_state.cable_length,
            'repetition_count': st.session_state.repetition_count
        }
        st.session_state.saved_recipes[save_name] = data_to_save
        st.success(f"'{save_name}' 이름으로 현재 모든 설정이 저장되었습니다!")
    elif st.session_state.input_df.empty:
        st.warning("저장할 레시피가 비어있습니다.")
    else:
        st.warning("저장할 레시피 이름을 입력해주세요.")

if 'saved_recipes' in st.session_state and st.session_state.saved_recipes:
    st.markdown("---")
    st.subheader("현재 저장된 레시피 목록")
    st.write(list(st.session_state.saved_recipes.keys()))
    if st.button("⚠️ 저장된 모든 레시피 삭제"):
        st.session_state.saved_recipes = {}
        st.rerun()

