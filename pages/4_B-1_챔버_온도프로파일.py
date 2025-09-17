import streamlit as st
import pandas as pd
import numpy as np
import math

# --- 0. 기본 설정 ---
st.set_page_config(layout="wide")
st.title("🌡️ 챔버 온도 프로파일 계산기")
st.info("이 페이지의 계산 결과는 'B_챔버 설정 및 계산' 페이지의 사양을 기반으로 합니다.")


# --- 1. 필요한 모든 데이터와 계산 함수를 이 파일에 직접 정의 ---

K_VALUES = {"우레탄폼": 0.023, "글라스울": 0.040, "세라크울": 0.150}
DENSITY_SUS = 7930
COP_TABLE_1STAGE = {10: 4.0, 0: 3.0, -10: 2.2, -20: 1.5, -25: 1.2}
COP_TABLE_2STAGE = {-20: 2.5, -30: 2.0, -40: 1.5, -50: 1.1, -60: 0.8, -70: 0.5}

def calculate_chamber_power(specs):
    """
    주어진 사양(specs)으로 가열/냉각 모드를 자동 판단하고,
    최소 구동 부하율을 반영하여 소비 전력(kW)을 계산하는 함수.
    """
    try:
        # --- 사양 추출 ---
        chamber_w = specs.get('chamber_w', 1000); chamber_d = specs.get('chamber_d', 1000); chamber_h = specs.get('chamber_h', 1000)
        insulation_type = specs.get('insulation_type', '우레탄폼'); insulation_thickness = specs.get('insulation_thickness', 100)
        target_temp = specs.get('target_temp', 25.0); outside_temp = specs.get('outside_temp', 25.0)
        load_type = specs.get('load_type', '없음'); num_cells = specs.get('num_cells', 0)
        fan_motor_load = specs.get('fan_motor_load', 0.5); fan_soak_factor = specs.get('fan_soak_factor', 30)
        min_soak_load_factor = specs.get('min_soak_load_factor', 30)
        sus_thickness = specs.get('sus_thickness', 1.2); ramp_rate = specs.get('ramp_rate', 1.0)
        refrigeration_system = specs.get('refrigeration_system', '1원 냉동')
        safety_factor = specs.get('safety_factor', 1.5)
        heater_capacity = specs.get('heater_capacity', 5.0)

        # --- 기본 부하 계산 ---
        k_value = K_VALUES.get(insulation_type, 0.023)
        thickness_m = insulation_thickness / 1000.0
        U_value = (k_value / thickness_m) if thickness_m > 0 else 0
        A = 2 * ((chamber_w * chamber_d) + (chamber_w * chamber_h) + (chamber_d * chamber_h)) / 1_000_000
        delta_T_abs = abs(target_temp - outside_temp)
        conduction_load_abs = U_value * A * delta_T_abs

        sus_volume_m3 = A * (sus_thickness / 1000.0)
        calculated_internal_mass = sus_volume_m3 * DENSITY_SUS
        volume_m3 = (chamber_w * chamber_d * chamber_h) / 1_000_000_000
        ramp_rate_c_per_sec = ramp_rate / 60.0
        
        ramp_load_energy_per_c = (volume_m3 * 1.225 * 1005) + (calculated_internal_mass * 500)
        ramp_load_w = ramp_load_energy_per_c * ramp_rate_c_per_sec

        internal_product_load_w = num_cells * 50.0 if load_type == '각형 배터리' else 0.0
        fan_motor_load_w_ramp = fan_motor_load * 1000
        fan_motor_load_w_soak = fan_motor_load_w_ramp * (fan_soak_factor / 100.0)

        is_heating = target_temp > outside_temp

        if is_heating:
            # --- 가열 모드 ---
            internal_gains_ramp = fan_motor_load_w_ramp + internal_product_load_w
            theoretical_heater_power_ramp_w = max(0, conduction_load_abs + ramp_load_w - internal_gains_ramp)
            min_heater_power_ramp_kw = heater_capacity * (min_soak_load_factor / 100.0)
            final_heater_power_ramp_w = max(theoretical_heater_power_ramp_w, min_heater_power_ramp_kw * 1000)
            total_consumption_ramp_kw = (final_heater_power_ramp_w / 1000) + fan_motor_load

            internal_gains_soak = fan_motor_load_w_soak + internal_product_load_w
            theoretical_heater_power_soak_w = max(0, conduction_load_abs - internal_gains_soak)
            min_heater_power_soak_kw = heater_capacity * (min_soak_load_factor / 100.0)
            final_heater_power_soak_w = max(theoretical_heater_power_soak_w, min_heater_power_soak_kw * 1000)
            total_consumption_soak_kw = (final_heater_power_soak_w / 1000) + (fan_motor_load * (fan_soak_factor / 100.0))

        else:
            # --- 냉각 모드 ---
            if target_temp > -25:
                sorted_cop_items = sorted(COP_TABLE_1STAGE.items())
            else:
                sorted_cop_items = sorted(COP_TABLE_2STAGE.items())
            
            total_heat_load_ramp = conduction_load_abs + ramp_load_w + internal_product_load_w + fan_motor_load_w_ramp
            total_heat_load_soak = conduction_load_abs + internal_product_load_w + fan_motor_load_w_soak

            cop = np.interp(target_temp, [k for k,v in sorted_cop_items], [v for k,v in sorted_cop_items])

            required_electrical_power_ramp = total_heat_load_ramp / cop if cop > 0 else float('inf')
            required_hp_ramp = (required_electrical_power_ramp * safety_factor) / 746
            required_electrical_power_soak = total_heat_load_soak / cop if cop > 0 else float('inf')
            required_hp_soak = (required_electrical_power_soak * safety_factor) / 746

            actual_hp, actual_rated_power = 0, 0
            if refrigeration_system == '1원 냉동':
                actual_hp = specs.get('actual_hp_1stage', 5.0); actual_rated_power = specs.get('actual_rated_power_1stage', 3.5)
            elif refrigeration_system == '2원 냉동':
                if target_temp > -25:
                    actual_hp = specs.get('actual_hp_2stage_h', 3.0); actual_rated_power = specs.get('actual_rated_power_2stage_h', 2.0)
                else:
                    actual_hp = specs.get('actual_hp_2stage_h', 3.0) + specs.get('actual_hp_2stage_l', 2.0)
                    actual_rated_power = specs.get('actual_rated_power_2stage_h', 2.0) + specs.get('actual_rated_power_2stage_l', 1.5)

            min_load_power_ramp_kw = actual_rated_power * (min_soak_load_factor / 100.0)
            theoretical_power_ramp_kw = actual_rated_power * (required_hp_ramp / actual_hp) if actual_hp > 0 else 0
            final_estimated_power_ramp_kw = max(min_load_power_ramp_kw, theoretical_power_ramp_kw)
            
            min_load_power_soak_kw = actual_rated_power * (min_soak_load_factor / 100.0)
            theoretical_power_soak_kw = actual_rated_power * (required_hp_soak / actual_hp) if actual_hp > 0 else 0
            final_estimated_power_soak_kw = max(min_load_power_soak_kw, theoretical_power_soak_kw)

            total_consumption_ramp_kw = final_estimated_power_ramp_kw + fan_motor_load
            total_consumption_soak_kw = final_estimated_power_soak_kw + (fan_motor_load * (fan_soak_factor / 100.0))

        return {"power_ramp_kw": total_consumption_ramp_kw, "power_soak_kw": total_consumption_soak_kw}

    except Exception:
        return {"power_ramp_kw": 0, "power_soak_kw": 0}

# --- 2. st.session_state 초기화 ---
if 'profile_df' not in st.session_state:
    st.session_state.profile_df = pd.DataFrame(
        [{"목표 온도 (°C)": 25.0, "유지 시간 (H)": 1.0}],
        columns=["목표 온도 (°C)", "유지 시간 (H)"]
    )
defaults = {
    'initial_temp': 25.0,
    'chamber_count': 1,
    'profile_reps': 1
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- 3. 온도 프로파일 입력 UI ---
st.subheader("초기 조건 설정")
st.number_input("초기 챔버 실내 온도 (°C)", key='initial_temp')

# ★★★★★ 테스트 옵션 UI 추가 ★★★★★
st.subheader("테스트 옵션")
col1, col2 = st.columns(2)
with col1:
    st.number_input("챔버 ROOM 개수", min_value=1, step=1, key='chamber_count')
with col2:
    st.number_input("프로파일 반복 횟수", min_value=1, step=1, key='profile_reps')
# ★★★★★ UI 추가 끝 ★★★★★


st.subheader("온도 프로파일 구성 테이블")

chamber_specs = st.session_state.get("chamber_specs", {})
with st.expander("🔍 'B 페이지'에서 불러온 데이터 확인 (디버깅용)"):
    st.json(chamber_specs)

min_temp_limit = chamber_specs.get('min_temp_spec', -100.0)
max_temp_limit = chamber_specs.get('max_temp_spec', 200.0)

st.info(f"입력 가능한 온도 범위: **{min_temp_limit}°C ~ {max_temp_limit}°C** (챔버 사양 기준)")

if st.button("➕ 스텝 추가"):
    new_step = pd.DataFrame([{"목표 온도 (°C)": 25.0, "유지 시간 (H)": 1.0}])
    st.session_state.profile_df = pd.concat([st.session_state.profile_df, new_step], ignore_index=True)
    st.rerun()

st.session_state.profile_df['목표 온도 (°C)'] = st.session_state.profile_df['목표 온도 (°C)'].fillna(25.0)

edited_df = st.data_editor(
    st.session_state.profile_df,
    column_config={
        "목표 온도 (°C)": st.column_config.NumberColumn(
            "목표 온도 (°C)", min_value=min_temp_limit, max_value=max_temp_limit,
            format="%.1f", required=True
        ),
        "유지 시간 (H)": st.column_config.NumberColumn(
            "유지 시간 (H)", help="'Soak' 상태일 때의 유지 시간을 입력합니다.", format="%.2f"
        ),
    },
    num_rows="dynamic",
    hide_index=True
)
st.session_state.profile_df = edited_df

# --- 4. 자동 계산 로직 ---
if st.button("⚙️ 프로파일 계산 실행"):
    if "chamber_specs" not in st.session_state or not st.session_state["chamber_specs"]:
        st.warning("⚠️ 먼저 'B_챔버 설정 및 계산' 페이지에서 챔버 사양을 저장해주세요.")
    else:
        try:
            chamber_specs_original = st.session_state["chamber_specs"].copy()
            
            # ★★★★★ 반복 횟수 적용 ★★★★★
            reps = st.session_state.profile_reps
            if not edited_df.empty:
                profile_to_calc = pd.concat([edited_df.copy()] * reps, ignore_index=True)
            else:
                profile_to_calc = edited_df.copy()
            
            results = []
            total_time = 0.0
            total_kwh_single_chamber = 0.0
            current_temp = st.session_state.initial_temp
            
            for index, row in profile_to_calc.iterrows():
                target_temp_step = row['목표 온도 (°C)']
                soak_time = row['유지 시간 (H)']
                
                if pd.isna(target_temp_step):
                    continue

                specs_for_step = chamber_specs_original.copy()
                specs_for_step['target_temp'] = target_temp_step
                specs_for_step['outside_temp'] = chamber_specs_original.get('outside_temp', 25.0)

                # Ramp 구간 계산
                if target_temp_step != current_temp:
                    delta_t = abs(target_temp_step - current_temp)
                    ramp_rate = chamber_specs_original.get('ramp_rate', 1.0)
                    ramp_time = (delta_t / ramp_rate) / 60.0 if ramp_rate > 0 else 0
                    
                    avg_ramp_temp = (current_temp + target_temp_step) / 2
                    specs_for_ramp = specs_for_step.copy()
                    specs_for_ramp['target_temp'] = avg_ramp_temp

                    power_values = calculate_chamber_power(specs_for_ramp)
                    power_ramp_kw = power_values['power_ramp_kw']
                    
                    ramp_kwh = power_ramp_kw * ramp_time
                    total_time += ramp_time
                    total_kwh_single_chamber += ramp_kwh
                    results.append([f"반복 {index // len(edited_df) + 1} - 스텝 {index % len(edited_df) + 1} Ramp", f"{current_temp:.1f} → {target_temp_step:.1f}", f"{ramp_time:.2f}", f"{ramp_kwh:.2f}"])
                    current_temp = target_temp_step

                # Soak 구간 계산
                if pd.notna(soak_time) and soak_time > 0:
                    power_values = calculate_chamber_power(specs_for_step)
                    power_soak_kw = power_values['power_soak_kw']
                    soak_kwh = power_soak_kw * soak_time
                    total_time += soak_time
                    total_kwh_single_chamber += soak_kwh
                    results.append([f"반복 {index // len(edited_df) + 1} - 스텝 {index % len(edited_df) + 1} Soak", f"{current_temp:.1f} 유지", f"{soak_time:.2f}", f"{soak_kwh:.2f}"])
            
            # ★★★★★ 최종 결과 저장 ★★★★★
            st.session_state.chamber_profile_time = total_time
            st.session_state.single_chamber_kwh = total_kwh_single_chamber
            st.session_state.total_kwh_all_chambers = total_kwh_single_chamber * st.session_state.chamber_count
            st.session_state.profile_results = results
            st.success("프로파일 계산이 완료되었습니다!")

        except Exception as e:
            st.error(f"계산 중 오류가 발생했습니다: {e}")
            st.exception(e)

# --- 5. 결과 표시 ---
st.markdown("---")
st.subheader("프로파일 계산 결과")

if 'profile_results' in st.session_state and st.session_state.profile_results:
    results = st.session_state.profile_results
    if results:
        result_df = pd.DataFrame(results, columns=["구간", "내용", "소요 시간(H)", "소비 전력량(kWh)"])
        st.dataframe(result_df)
    
    # ★★★★★ 수정된 결과 요약 UI ★★★★★
    st.info(f"계산 기준: 챔버 {st.session_state.chamber_count}대, 프로파일 {st.session_state.profile_reps}회 반복")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("프로파일 총 소요 시간 (H)", f"{st.session_state.get('chamber_profile_time', 0):.2f}")
    with col2:
        st.metric("챔버 1ROOM 총 전력량 (kWh)", f"{st.session_state.get('single_chamber_kwh', 0):.2f}")
    with col3:
        st.metric(f"챔버 {st.session_state.chamber_count}ROOM 총 전력량 (kWh)", f"{st.session_state.get('total_kwh_all_chambers', 0):.2f}")

