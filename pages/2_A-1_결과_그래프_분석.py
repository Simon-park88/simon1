import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
import math
from bisect import bisect_right
from scipy.interpolate import griddata

# --- 0. 기본 설정 및 한글 폰트 ---
st.set_page_config(layout="wide")

# Matplotlib 한글 폰트 설정
try:
    font_path_list = fm.findSystemFonts(fontpaths=None, fontext='ttf')
    kor_font_names = ['malgun gothic', 'apple sd gothic neo', 'nanumgothic', '맑은 고딕']
    kor_font_path = ""
    for font_path in font_path_list:
        font_name = fm.FontProperties(fname=font_path).get_name().lower()
        if any(kor_name in font_name for kor_name in kor_font_names):
            kor_font_path = font_path
            break
    if kor_font_path:
        font_name = fm.FontProperties(fname=kor_font_path).get_name()
        plt.rc('font', family=font_name)
except Exception:
    st.warning("한글 폰트를 찾는 데 문제가 발생했습니다. 그래프의 글자가 깨질 수 있습니다.")
plt.rc('axes', unicode_minus=False)


# --- 1. 효율 데이터 테이블 및 계산 함수 정의 (계산기와 동일) ---
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

# --- 2. 계산 함수 (최신 로직으로 업데이트) ---
def calculate_power_profile(input_df, specs):
    calculated_df = input_df.copy()
    
    # 사양 로드
    cell_capacity = specs.get('cell_capacity', 211.1)
    equipment_spec = specs.get('equipment_spec', '60A - 300A')
    control_channels = specs.get('control_channels', 16)
    standby_power = specs.get('standby_power', 1572.0)
    test_channels = specs.get('test_channels', 800)
    cable_length = specs.get('cable_length', 3.0)
    cable_area = specs.get('cable_area', 150.0)
    cp_cccv_details = specs.get('cp_cccv_details', {})
    
    required_equipment = math.ceil(test_channels / control_channels) if control_channels > 0 else 0
    max_capacity_ah = cell_capacity
    current_charge_ah = 0.0
    
    calculated_columns = ["C-rate", "실제 테스트 시간(H)", "효율(%)", "전력(kW)", "전력량(kWh)", "누적 충전량(Ah)", "SoC(%)"]
    for col in calculated_columns: calculated_df[col] = 0.0

    for index, row in calculated_df.iterrows():
        original_index = index % len(input_df) if len(input_df) > 0 else 0
        mode = row['모드']; test_type = row['테스트']

        if mode == 'Rest':
            time_limit = row['시간 제한(H)']; actual_time = time_limit if pd.notna(time_limit) else 0.0
            total_power_w = standby_power * required_equipment; total_power_kw = total_power_w / 1000.0
            kwh = total_power_kw * actual_time
            soc_val = (current_charge_ah / max_capacity_ah) * 100 if max_capacity_ah > 0 else 0
            calculated_df.loc[index, ['실제 테스트 시간(H)', '전력(kW)', '전력량(kWh)', '누적 충전량(Ah)', 'SoC(%)']] = [actual_time, total_power_kw, kwh, current_charge_ah, soc_val]

        elif test_type == 'CCCV' and mode == 'Charge':
            details = cp_cccv_details.get(original_index, {})
            if not details: continue

            cc_current = row['전류(A)']; avg_v_cc = row['전압(V)'] if pd.notna(row['전압(V)']) else 3.8
            cv_v = details.get('cv_v'); cutoff_a = details.get('cutoff_a'); transition_ratio = details.get('transition', 80.0) / 100.0

            chargeable_ah = max_capacity_ah - current_charge_ah
            ah_for_cc = chargeable_ah * transition_ratio
            ah_for_cv = chargeable_ah * (1 - transition_ratio)

            time_cc = ah_for_cc / cc_current if cc_current > 0 else 0
            avg_current_cv = (cc_current + cutoff_a) / 2.0 if cc_current and cutoff_a else 0
            time_cv = ah_for_cv / avg_current_cv if avg_current_cv > 0 else 0
            
            calculated_full_time = time_cc + time_cv
            time_limit = row['시간 제한(H)']
            
            actual_time = calculated_full_time
            if pd.notna(time_limit) and time_limit > 0 and time_limit < calculated_full_time:
                actual_time = time_limit
            
            time_spent_in_cc, time_spent_in_cv = 0, 0
            if actual_time <= time_cc:
                time_spent_in_cc = actual_time
                actual_charge_change = time_spent_in_cc * cc_current
            else:
                time_spent_in_cc = time_cc
                time_spent_in_cv = actual_time - time_cc
                actual_charge_change = ah_for_cc + (time_spent_in_cv * avg_current_cv)

            eff_cc = get_efficiency(mode, avg_v_cc, cc_current, equipment_spec, cable_length, cable_area)
            p_out_cc = avg_v_cc * cc_current
            p_in_cc = p_out_cc / eff_cc if eff_cc > 0 else 0
            
            eff_cv = get_efficiency(mode, cv_v, avg_current_cv, equipment_spec, cable_length, cable_area)
            p_out_cv = cv_v * avg_current_cv
            p_in_cv = p_out_cv / eff_cv if eff_cv > 0 else 0
            
            total_energy_wh_in = (p_in_cc * time_spent_in_cc) + (p_in_cv * time_spent_in_cv)
            avg_p_in_w = total_energy_wh_in / actual_time if actual_time > 0 else 0
            
            num_full = test_channels // control_channels
            rem_ch = test_channels % control_channels
            p_full_total = num_full * ((avg_p_in_w * control_channels) + standby_power)
            p_partial = (avg_p_in_w * rem_ch) + standby_power if rem_ch > 0 else 0
            total_power_w = p_full_total + p_partial
            total_power_kw = total_power_w / 1000.0
            kwh = total_power_kw * actual_time
            
            current_charge_ah += actual_charge_change
            current_charge_ah = np.clip(current_charge_ah, 0, max_capacity_ah)
            soc_percent = (current_charge_ah / max_capacity_ah) * 100 if max_capacity_ah > 0 else 0

            calculated_df.loc[index, ['실제 테스트 시간(H)', '누적 충전량(Ah)', 'SoC(%)', '전력(kW)', '전력량(kWh)']] = \
                [actual_time, current_charge_ah, soc_percent, total_power_kw, kwh]

        elif mode in ['Charge', 'Discharge']: # CC, CP 처리
            voltage, current, power_w = row['전압(V)'], row['전류(A)'], row['전력(W)']
            
            if test_type == 'CC': current = abs(row['전류(A)']) if pd.notna(row['전류(A)']) else 0
            elif test_type == 'CP':
                avg_v = None
                details = cp_cccv_details.get(original_index)
                if details:
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
                efficiency = get_efficiency(mode, voltage, current, equipment_spec, cable_length, cable_area)
                time_limit = row['시간 제한(H)']; c_rate = current / cell_capacity if cell_capacity > 0 else 0
                c_rate_time = cell_capacity / current if current > 0 else float('inf')
                
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
                    num_full = test_channels // control_channels; rem_ch = test_channels % control_channels
                    p_full_total = num_full * ((p_in_w * control_channels) + standby_power)
                    p_partial = (p_in_w * rem_ch) + standby_power if rem_ch > 0 else 0
                    total_power_kw = (p_full_total + p_partial) / 1000.0
                else: # Discharge
                    # ★★★★★ 수정된 부분: 대기전력을 고려한 방전 전력 계산 ★★★★★
                    p_rec_w = voltage * current * efficiency
                    total_rec_w = p_rec_w * test_channels
                    total_standby_w = standby_power * required_equipment
                    total_power_w = total_standby_w - total_rec_w
                    total_power_kw = total_power_w / 1000.0
                
                kwh = total_power_kw * actual_time
                calculated_df.loc[index, ['C-rate', '효율(%)', '실제 테스트 시간(H)', '누적 충전량(Ah)', 'SoC(%)', '전력(kW)', '전력량(kWh)']] = \
                    [c_rate, efficiency * 100.0, actual_time, current_charge_ah, soc_percent, total_power_kw, kwh]
    return calculated_df

def get_power_at_time(t, time_data, power_data):
    idx = bisect_right(time_data, t)
    if idx == 0: return 0
    return power_data[idx - 1]

# --- 3. 메인 앱 UI ---
st.title("📊 저장된 레시피 비교 분석")

if 'saved_recipes' not in st.session_state or not st.session_state.saved_recipes:
    st.warning("분석할 저장된 레시피가 없습니다. '레시피 계산기' 페이지에서 먼저 레시피를 저장해주세요.")
else:
    st.sidebar.header("그래프 옵션")
    selected_recipe_names = st.multiselect(
        "그래프로 비교할 레시피를 선택하세요",
        options=list(st.session_state.saved_recipes.keys())
    )
    
    repetition_counts = {}
    if selected_recipe_names:
        st.sidebar.header("개별 반복 횟수 설정")
        for name in selected_recipe_names:
            default_value = st.session_state.saved_recipes[name].get('repetition_count', 1)
            repetition_counts[name] = st.sidebar.number_input(
                f"'{name}' 반복 횟수", min_value=1, step=1, value=default_value, key=f"rep_{name}"
            )

    if selected_recipe_names:
        fig, ax = plt.subplots(figsize=(16, 8))
        all_recipe_coords = []
        all_time_points = {0.0}
        individual_peaks = {}

        for name in selected_recipe_names:
            saved_data = st.session_state.saved_recipes[name]
            
            individual_repetition_count = repetition_counts.get(name, 1)
            recipe_df = saved_data.get('recipe_table')

            if recipe_df is not None and not recipe_df.empty:
                recipe_to_calc = pd.concat([recipe_df.copy()] * individual_repetition_count, ignore_index=True)
                
                result_df = calculate_power_profile(recipe_to_calc, saved_data)
                
                single_run_profile = result_df[['실제 테스트 시간(H)', '전력(kW)']].values.tolist()
                
                time_points, power_values = [0.0], []
                current_time = 0.0
                if single_run_profile:
                    power_values.append(single_run_profile[0][1])

                for step_time, step_power in single_run_profile:
                    if power_values:
                        time_points.append(current_time)
                        power_values.append(power_values[-1])
                    time_points.append(current_time)
                    power_values.append(step_power)
                    current_time += step_time
                    time_points.append(current_time)
                    power_values.append(step_power)
                    all_time_points.add(current_time)
                    
                individual_peaks[name] = max(p for p in power_values if p >= 0) if any(p >= 0 for p in power_values) else 0
                all_recipe_coords.append({'name': name, 'times': time_points, 'powers': power_values})
                ax.plot(time_points, power_values, linestyle='--', alpha=0.4, label=f"{name} ({individual_repetition_count}회 반복)")

        if all_recipe_coords:
            unified_timeline = sorted(list(all_time_points))
            time_combined, power_combined = [], []
            for t in unified_timeline:
                current_total_power = sum(get_power_at_time(t, recipe['times'], recipe['powers']) for recipe in all_recipe_coords)
                time_combined.append(t)
                power_combined.append(current_total_power)

            final_time_combined, final_power_combined = [], []
            if time_combined:
                final_power_combined.append(power_combined[0])
                for i in range(len(time_combined) - 1):
                    final_time_combined.extend([time_combined[i], time_combined[i + 1]])
                    final_power_combined.extend([power_combined[i], power_combined[i]])
                final_time_combined.append(time_combined[-1])

            ax.plot(final_time_combined, final_power_combined, linestyle='-', color='black', linewidth=2.5, label='종합 전력')

            if power_combined:
                peak_power_after_5h, peak_time_after_5h = -float('inf'), 0
                for t, p in zip(time_combined, power_combined):
                    if t > 5.0 and p > peak_power_after_5h:
                        peak_power_after_5h, peak_time_after_5h = p, t
                if peak_time_after_5h > 0:
                    ax.plot(peak_time_after_5h, peak_power_after_5h, 'ro', markersize=8)
                    annotation_text = f'최대 피크 (5H 이후)\n시간: {peak_time_after_5h:.2f}H\n전력: {peak_power_after_5h:.2f}kW'
                    ax.annotate(annotation_text, xy=(peak_time_after_5h, peak_power_after_5h),
                                xytext=(peak_time_after_5h + 5, peak_power_after_5h),
                                fontsize=12, ha='left', va='center',
                                bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                                arrowprops=dict(facecolor='red', shrink=0.05, width=2))
            
            ax.set_title(f'저장된 레시피 비교 및 종합 전력 분석', fontsize=18)
            ax.set_xlabel('총 경과 시간 (H)'); ax.set_ylabel('전력 (kW)')
            ax.axhline(0, color='black', linestyle='-', linewidth=0.8)
            ax.grid(True, linestyle='--', alpha=0.5); ax.legend(); ax.set_xlim(left=0)
            st.pyplot(fig)

            st.markdown("---")
            st.subheader("개별 레시피 피크 정보")
            num_recipes = len(individual_peaks)
            cols = st.columns(num_recipes if num_recipes > 0 and num_recipes <= 4 else 4)
            i = 0
            for name, peak in individual_peaks.items():
                with cols[i % 4]:
                    st.metric(label=f"'{name}' 최대 피크", value=f"{peak:.2f} kW")
                i += 1

            if power_combined:
                st.markdown("---")
                st.subheader("종합 전력 분석 결과")
                overall_peak_power = max(p for p in power_combined if p >= 0) if any(p >= 0 for p in power_combined) else 0
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("전체 기간 최대 피크 (kW)", f"{overall_peak_power:.2f}")
                with col2:
                    if peak_time_after_5h > 0:
                        st.metric("최대 피크 (5H 이후)", f"{peak_power_after_5h:.2f} kW", delta=f"{peak_time_after_5h:.2f} H 시점")

