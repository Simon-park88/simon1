import streamlit as st
import pandas as pd
import numpy as np
import math

# --- 0. 기본 설정 ---
st.set_page_config(layout="wide")
st.title("🌡️ 챔버 온도 프로파일 계산기")
st.info("이 페이지의 계산 결과는 'B_챔버 설정 및 계산' 페이지에서 선택한 사양을 기반으로 합니다.")

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

# --- 2. st.session_state 초기화 및 콜백 함수 ---
if 'profile_df' not in st.session_state:
    st.session_state.profile_df = pd.DataFrame(
        [{"목표 온도 (°C)": 25.0, "유지 시간 (H)": 1.0}],
        columns=["목표 온도 (°C)", "유지 시간 (H)"]
    )
if 'saved_chamber_profiles' not in st.session_state:
    st.session_state.saved_chamber_profiles = {}
    
defaults = {
    'initial_temp': 25.0,
    'chamber_count': 1,
    'profile_reps': 1,
    'selected_spec_for_profile': None,
    'profile_to_load': "선택하세요" 
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

def load_chamber_profile_callback():
    """선택된 프로파일을 session_state로 불러오는 콜백 함수"""
    profile_name = st.session_state.profile_to_load
    if profile_name != "선택하세요" and profile_name in st.session_state.saved_chamber_profiles:
        loaded_data = st.session_state.saved_chamber_profiles[profile_name]
        
        st.session_state.initial_temp = loaded_data.get('initial_temp', 25.0)
        st.session_state.chamber_count = loaded_data.get('chamber_count', 1)
        st.session_state.profile_reps = loaded_data.get('profile_reps', 1)
        st.session_state.selected_spec_for_profile = loaded_data.get('source_chamber_spec', None)
        
        if 'profile_df' in loaded_data and isinstance(loaded_data['profile_df'], list):
            st.session_state.profile_df = pd.DataFrame(loaded_data['profile_df'])
        
        st.success(f"'{profile_name}' 프로파일을 성공적으로 불러왔습니다!")

# ★★★★★ 추가: 저장된 프로파일 삭제 콜백 함수 ★★★★★
def delete_chamber_profile_callback():
    """선택된 프로파일을 삭제하는 콜백 함수"""
    profile_to_delete = st.session_state.profile_to_load
    if profile_to_delete != "선택하세요" and profile_to_delete in st.session_state.saved_chamber_profiles:
        del st.session_state.saved_chamber_profiles[profile_to_delete]
        st.session_state.profile_to_load = "선택하세요" # selectbox 상태 리셋
        st.success(f"'{profile_to_delete}' 프로파일을 삭제했습니다.")
    else:
        st.warning("삭제할 프로파일을 먼저 선택해주세요.")


# --- 3. UI 구성 ---
with st.expander("📂 저장된 프로파일 관리", expanded=True):
    if not st.session_state.saved_chamber_profiles:
        st.info("저장된 프로파일이 없습니다.")
    else:
        col_load1, col_load2, col_load3 = st.columns([0.6, 0.2, 0.2])
        with col_load1:
            st.selectbox("관리할 프로파일을 선택하세요", 
                         options=["선택하세요"] + list(st.session_state.saved_chamber_profiles.keys()), 
                         key="profile_to_load")
        with col_load2:
            st.button("📥 선택한 프로파일 불러오기", on_click=load_chamber_profile_callback, use_container_width=True)
        with col_load3:
            # ★★★★★ 수정: 삭제 버튼에 콜백 함수 연결 ★★★★★
            st.button("⚠️ 선택한 프로파일 삭제", on_click=delete_chamber_profile_callback, use_container_width=True)

st.markdown("---")


st.subheader("1. 계산 기반 챔버 사양 선택")
saved_chamber_specs = st.session_state.get('saved_chamber_specs', {})

if not saved_chamber_specs:
    st.error("⚠️ 먼저 'B_챔버 설정 및 계산' 페이지에서 챔버 사양을 저장해주세요. 페이지를 새로고침하여 다시 시도할 수 있습니다.")
    st.stop()

spec_options = list(saved_chamber_specs.keys())
try:
    current_index = spec_options.index(st.session_state.selected_spec_for_profile)
except (ValueError, TypeError):
    current_index = 0

st.selectbox(
    "계산에 사용할 챔버 사양을 선택하세요.",
    options=spec_options,
    key='selected_spec_for_profile',
    index=current_index
)

# --- 4. 온도 프로파일 입력 UI ---
st.subheader("2. 초기 조건 및 테스트 옵션")
col1, col2, col3 = st.columns(3)
with col1:
    st.number_input("초기 챔버 실내 온도 (°C)", key='initial_temp')
with col2:
    st.number_input("챔버 ROOM 개수", min_value=1, step=1, key='chamber_count')
with col3:
    st.number_input("프로파일 반복 횟수", min_value=1, step=1, key='profile_reps')


st.subheader("3. 온도 프로파일 구성 테이블")

selected_spec_name = st.session_state.selected_spec_for_profile
chamber_specs_for_profile = saved_chamber_specs.get(selected_spec_name, {})

with st.expander("🔍 현재 적용된 챔버 사양 데이터 확인 (디버깅용)"):
    st.json(chamber_specs_for_profile)

min_temp_limit = chamber_specs_for_profile.get('min_temp_spec', -100.0)
max_temp_limit = chamber_specs_for_profile.get('max_temp_spec', 200.0)

st.info(f"입력 가능한 온도 범위: **{min_temp_limit}°C ~ {max_temp_limit}°C** ('{selected_spec_name}' 사양 기준)")

if st.button("➕ 스텝 추가"):
    new_step = pd.DataFrame([{"목표 온도 (°C)": 25.0, "유지 시간 (H)": 1.0}])
    st.session_state.profile_df = pd.concat([st.session_state.profile_df, new_step], ignore_index=True)

edited_df = st.data_editor(
    st.session_state.profile_df,
    column_config={
        "목표 온도 (°C)": st.column_config.NumberColumn(
            "목표 온도 (°C)", min_value=min_temp_limit, max_value=max_temp_limit,
            format="%.1f", required=True
        ),
        "유지 시간 (H)": st.column_config.NumberColumn(
            "유지 시간 (H)", help="'Soak' 상태일 때의 유지 시간을 입력합니다.", format="%.2f", required=True
        ),
    },
    num_rows="dynamic",
    hide_index=True,
    key="profile_editor"
)

# --- 5. 자동 계산 로직 ---
if st.button("⚙️ 프로파일 계산 실행"):
    if not selected_spec_name or not chamber_specs_for_profile:
        st.warning("⚠️ 계산에 사용할 챔버 사양을 먼저 선택하고 저장해주세요.")
    else:
        try:
            edited_df['목표 온도 (°C)'] = pd.to_numeric(edited_df['목표 온도 (°C)'], errors='coerce')
            edited_df['유지 시간 (H)'] = pd.to_numeric(edited_df['유지 시간 (H)'], errors='coerce')
            edited_df.dropna(subset=['목표 온도 (°C)', '유지 시간 (H)'], inplace=True)
            st.session_state.profile_df = edited_df
            
            reps = st.session_state.profile_reps
            if not edited_df.empty:
                profile_to_calc = pd.concat([edited_df.copy()] * reps, ignore_index=True)
            else:
                st.warning("계산할 프로파일 스텝을 1개 이상 입력해주세요.")
                st.stop()
            
            results = []
            total_time = 0.0
            total_kwh_single_chamber = 0.0
            current_temp = st.session_state.initial_temp
            has_ramp = False
            
            for index, row in profile_to_calc.iterrows():
                target_temp_step = row['목표 온도 (°C)']
                soak_time = row['유지 시간 (H)']
                
                specs_for_step = chamber_specs_for_profile.copy()
                specs_for_step['target_temp'] = target_temp_step
                
                if target_temp_step != current_temp:
                    has_ramp = True
                    delta_t = abs(target_temp_step - current_temp)
                    ramp_rate = chamber_specs_for_profile.get('ramp_rate', 1.0)
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

                if soak_time > 0:
                    power_values = calculate_chamber_power(specs_for_step)
                    power_soak_kw = power_values['power_soak_kw']
                    soak_kwh = power_soak_kw * soak_time
                    total_time += soak_time
                    total_kwh_single_chamber += soak_kwh
                    results.append([f"반복 {index // len(edited_df) + 1} - 스텝 {index % len(edited_df) + 1} Soak", f"{current_temp:.1f} 유지", f"{soak_time:.2f}", f"{soak_kwh:.2f}"])
            
            if has_ramp:
                peak_power_for_profile = chamber_specs_for_profile.get('total_consumption_ramp_kw', 0)
            else:
                peak_power_for_profile = chamber_specs_for_profile.get('total_consumption_soak_kw', 0)
            
            st.session_state.profile_results = {
                "results_table": results,
                "total_time": total_time,
                "single_chamber_kwh": total_kwh_single_chamber,
                "total_kwh_all_chambers": total_kwh_single_chamber * st.session_state.chamber_count,
                "peak_power_kw": peak_power_for_profile * st.session_state.chamber_count
            }
            st.success("프로파일 계산이 완료되었습니다!")

        except Exception as e:
            st.error(f"계산 중 오류가 발생했습니다: {e}")
            st.exception(e)

# --- 6. 결과 표시 ---
st.markdown("---")
st.subheader("4. 프로파일 계산 결과")

if 'profile_results' in st.session_state and st.session_state.profile_results:
    res = st.session_state.profile_results
    result_df = pd.DataFrame(res["results_table"], columns=["구간", "내용", "소요 시간(H)", "소비 전력량(kWh)"])
    st.dataframe(result_df)
    
    st.info(f"계산 기준: 챔버 {st.session_state.chamber_count}대, 프로파일 {st.session_state.profile_reps}회 반복")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("프로파일 총 소요 시간 (H)", f"{res.get('total_time', 0):.2f}")
    col2.metric("챔버 1ROOM 총 전력량 (kWh)", f"{res.get('single_chamber_kwh', 0):.2f}")
    col3.metric(f"챔버 {st.session_state.chamber_count}ROOM 총 전력량 (kWh)", f"{res.get('total_kwh_all_chambers', 0):.2f}")

    # --- 7. 계산 결과 저장 ---
    st.markdown("---")
    with st.form("profile_save_form"):
        profile_name = st.text_input("저장할 운영 프로파일 이름")
        submitted = st.form_submit_button("💾 현재 운영 프로파일 저장하기")
        if submitted:
            if not profile_name:
                st.warning("프로파일 이름을 입력해주세요.")
            else:
                data_to_save = {
                    'source_chamber_spec': selected_spec_name,
                    'chamber_count': st.session_state.chamber_count,
                    'profile_reps': st.session_state.profile_reps,
                    'initial_temp': st.session_state.initial_temp,
                    'profile_df': st.session_state.profile_df.to_dict('records'),
                    'total_profile_hours': res.get('total_time', 0),
                    'total_profile_kwh': res.get('total_kwh_all_chambers', 0),
                    'peak_power_kw': res.get('peak_power_kw', 0)
                }
                st.session_state.saved_chamber_profiles[profile_name] = data_to_save
                st.success(f"'{profile_name}' 프로파일이 저장되었습니다.")

