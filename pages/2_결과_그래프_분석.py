import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
import math
from bisect import bisect_right

# --- 0. 기본 설정 및 분석 함수 ---

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
    st.warning("한글 폰트를 찾는 데 문제가 발생했습니다. 글자가 깨질 수 있습니다.")
plt.rc('axes', unicode_minus=False)


# --- 효율 데이터 테이블 및 계산 함수 정의 ---

# 충전 효율 실측 데이터 (300A 장비 기준)
charge_currents = np.array([0, 60, 100, 160, 300, 2500])
charge_voltages = np.array([3, 4])
charge_efficiencies = np.array([
    [90.00, 90.00], [72.40, 78.10], [69.50, 75.50], [64.90, 71.20],
    [55.40, 60.80], [50.00, 50.00]
]) / 100.0

# 방전 효율 실측 데이터 (300A 장비 기준)
discharge_currents = np.array([0, 60, 100, 160, 300, 2500])
discharge_voltages = np.array([3, 4])
discharge_efficiencies = np.array([
    [90.00, 90.00], [65.70, 76.00], [60.90, 68.00], [52.30, 64.30],
    [28.70, 46.40], [20.00, 20.00]
]) / 100.0


def interpolate_2d(x, y, x_points, y_points, z_values):
    """2중 선형 보간법을 수행하는 함수 (버그 수정 버전)"""
    x = np.clip(x, x_points[0], x_points[-1])
    y = np.clip(y, y_points[0], y_points[-1])

    x_indices = np.searchsorted(x_points, x, side='right')
    y_indices = np.searchsorted(y_points, y, side='right')

    x_idx = np.clip(x_indices - 1, 0, len(x_points) - 2)
    y_idx = np.clip(y_indices - 1, 0, len(y_points) - 2)

    x1, x2 = x_points[x_idx], x_points[x_idx + 1]
    y1, y2 = y_points[y_idx], y_points[y_idx + 1]

    z11, z12 = z_values[y_idx, x_idx], z_values[y_idx, x_idx + 1]
    z21, z22 = z_values[y_idx + 1, x_idx], z_values[y_idx + 1, x_idx + 1]

    fx_y1 = (z11 * (x2 - x) + z12 * (x - x1)) / (x2 - x1)
    fx_y2 = (z21 * (x2 - x) + z22 * (x - x1)) / (x2 - x1)

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


def calculate_power_profile(input_df, specs):
    """저장된 레시피와 사양으로 최종 전력 프로파일을 계산하는 함수"""
    calculated_df = input_df.copy()

    calculated_columns = ["C-rate", "실제 테스트 시간(H)", "효율(%)", "전력(kW)", "전력량(kWh)", "누적 충전량(Ah)", "SoC(%)"]
    for col in calculated_columns:
        calculated_df[col] = 0.0

    # 사양 추출
    cell_capacity = specs['cell_capacity']
    equipment_spec = specs['equipment_spec']
    voltage_drop_value = specs['drop_voltage']
    control_channels = specs['control_channels']
    standby_power = specs['standby_power']
    test_channels = specs['test_channels']
    required_equipment = math.ceil(test_channels / control_channels) if control_channels > 0 else 0

    # SoC 트래킹을 위한 변수 초기화
    current_charge_ah = 0.0
    # 각 행(스텝)을 순회하며 모든 값 재계산
    for index, row in calculated_df.iterrows():
        total_power_w = 0.0
        mode = row['모드']

        # 1. Rest 모드를 먼저 처리
        if mode == 'Rest':
            time_limit = row['시간 제한(H)']

            actual_time = time_limit if pd.notna(time_limit) else 0.0

            total_power_w = standby_power * required_equipment
            total_power_kw = total_power_w / 1000.0
            kwh = total_power_kw * actual_time

            # 계산된 값 업데이트
            calculated_df.at[index, '실제 테스트 시간(H)'] = actual_time
            calculated_df.at[index, '전력(kW)'] = total_power_kw
            calculated_df.at[index, '전력량(kWh)'] = kwh
            calculated_df.at[index, 'C-rate'] = 0.0
            calculated_df.at[index, '효율(%)'] = 0.0

        # 2. Charge 또는 Discharge 모드이면서, 전압/전류 값이 모두 있을 때만 계산
        elif mode in ['Charge', 'Discharge'] and pd.notna(row['전압(V)']) and pd.notna(row['전류(A)']):
            voltage = row['전압(V)']
            current = abs(row['전류(A)'])
            time_limit = row['시간 제한(H)']

            # C-rate 계산
            c_rate = 0.0
            if cell_capacity > 0:
                c_rate = current / cell_capacity
            calculated_df.at[index, 'C-rate'] = c_rate

            # 효율 계산
            efficiency = get_efficiency(mode, voltage, current, equipment_spec)
            calculated_df.at[index, '효율(%)'] = efficiency * 100.0

            # SoC를 고려한 실제 테스트 시간 계산
            actual_time = 0.0
            if current > 0:
                # ★★★★★ 변수 이름 수정 ★★★★★
                c_rate_time = cell_capacity / current

                if mode == 'Charge':
                    chargeable_ah = cell_capacity - current_charge_ah
                    soc_time_limit = chargeable_ah / current if current > 0 else float('inf')

                elif mode == 'Discharge':
                    dischargeable_ah = current_charge_ah
                    soc_time_limit = dischargeable_ah / current if current > 0 else float('inf')

                possible_times = [soc_time_limit, c_rate_time]
                if time_limit is not None and time_limit > 0:
                    possible_times.append(time_limit)

                actual_time = min(possible_times)

            calculated_df.at[index, '실제 테스트 시간(H)'] = actual_time

            # 현재 충전량 업데이트
            charge_change = actual_time * current
            if mode == 'Charge':
                current_charge_ah += charge_change
            elif mode == 'Discharge':
                current_charge_ah -= charge_change

            # ★★★★★ 변수 이름 수정 ★★★★★
            current_charge_ah = np.clip(current_charge_ah, 0, cell_capacity)

            calculated_df.at[index, '누적 충전량(Ah)'] = current_charge_ah
            soc_percent = (current_charge_ah / cell_capacity) * 100 if cell_capacity > 0 else 0
            calculated_df.at[index, 'SoC(%)'] = soc_percent

            # 전력(kW) 계산
            total_power_kw = 0.0
            if mode == 'Charge':
                power_per_channel_w = ((voltage + voltage_drop_value) * current) / efficiency if efficiency > 0 else 0
                if control_channels > 0:
                    num_full_equip = test_channels // control_channels
                    remaining_channels = test_channels % control_channels
                    power_full_equip_total = num_full_equip * ((power_per_channel_w * control_channels) + standby_power)
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

            calculated_df.at[index, '전력(kW)'] = total_power_kw

            # 전력량(kWh) 계산
            kwh = total_power_kw * actual_time
            calculated_df.at[index, '전력량(kWh)'] = kwh

    return calculated_df

def get_power_at_time(t, time_data, power_data):
    idx = bisect_right(time_data, t)
    if idx == 0: return 0
    return power_data[idx - 1]


# --- 1. 메인 앱 UI ---
st.set_page_config(layout="wide")
st.title("📊 저장된 레시피 비교 분석")

if 'saved_recipes' not in st.session_state or not st.session_state.saved_recipes:
    st.warning("분석할 저장된 레시피가 없습니다. '레시피 계산기' 페이지에서 먼저 레시피를 저장해주세요.")
else:
    # --- ★★★★★ 반복 옵션 UI 추가 ★★★★★ ---
    st.sidebar.header("그래프 옵션")
    run_repetition = st.sidebar.toggle('반복 테스트', help="선택된 레시피들을 아래 횟수만큼 반복하여 전체 그래프를 그립니다.")
    repetition_count = 1
    if run_repetition:
        repetition_count = st.sidebar.number_input('반복 횟수', min_value=1, step=1, value=3)

    selected_recipe_names = st.multiselect(
        "그래프로 비교할 레시피를 선택하세요",
        options=list(st.session_state.saved_recipes.keys())
    )

    # --- ★★★★★ 개별 반복 횟수 설정 UI ★★★★★ ---
    repetition_counts = {}
    if selected_recipe_names:
        st.sidebar.header("개별 반복 횟수 설정")
        # session_state에 반복 횟수 저장 공간이 없으면 생성
        if 'repetition_counts' not in st.session_state:
            st.session_state.repetition_counts = {}

        # 선택된 각 레시피에 대해 숫자 입력창 생성
        for name in selected_recipe_names:
            # 이전에 입력한 값을 기억하도록 session_state 활용
            default_value = st.session_state.repetition_counts.get(name, 1)
            repetition_counts[name] = st.sidebar.number_input(
                f"'{name}' 반복 횟수",
                min_value=1,
                step=1,
                value=default_value,
                key=f"rep_{name}"  # 각 입력창을 구분하기 위한 고유 키
            )
            # 새로 입력된 값을 session_state에 업데이트
            st.session_state.repetition_counts[name] = repetition_counts[name]

    # --- 그래프 생성 로직 ---
    if selected_recipe_names:
        fig, ax = plt.subplots(figsize=(16, 8))
        all_recipe_coords = []
        all_time_points = {0.0}

        for name in selected_recipe_names:
            saved_data = st.session_state.saved_recipes[name]

            result_df = calculate_power_profile(saved_data['recipe_table'], saved_data)
            single_run_profile = result_df[['실제 테스트 시간(H)', '전력(kW)']].values.tolist()

            # ★★★★★ 개별 반복 횟수 적용 ★★★★★
            individual_repetition_count = repetition_counts.get(name, 1)
            full_run_profile = single_run_profile * individual_repetition_count

            # 확장된 프로파일로 그래프 좌표 생성
            time_points, power_values = [0.0], []
            current_time = 0.0

            # 계단식 그래프를 위한 첫 포인트 추가
            if full_run_profile:
                power_values.append(full_run_profile[0][1])

            for step_time, step_power in full_run_profile:
                time_points.append(current_time)
                power_values.append(power_values[-1])
                time_points.append(current_time)
                power_values.append(step_power)
                current_time += step_time
                time_points.append(current_time)
                power_values.append(step_power)
                all_time_points.add(current_time)

            all_recipe_coords.append({'name': name, 'times': time_points, 'powers': power_values})
            ax.plot(time_points, power_values, linestyle='--', alpha=0.4, label=f"{name} ({repetition_count}회 반복)")

        # 종합 전력 계산
        unified_timeline = sorted(list(all_time_points))
        time_combined, power_combined = [], []
        for t in unified_timeline:
            current_total_power = sum(
                get_power_at_time(t, recipe['times'], recipe['powers']) for recipe in all_recipe_coords)
            time_combined.append(t)
            power_combined.append(current_total_power)

        # 계단식 그래프를 위한 좌표 처리
        final_time_combined, final_power_combined = [], []
        for i in range(len(time_combined) - 1):
            final_time_combined.extend([time_combined[i], time_combined[i + 1]])
            final_power_combined.extend([power_combined[i], power_combined[i]])

        ax.plot(final_time_combined, final_power_combined, linestyle='-', color='black', linewidth=2.5, label='종합 전력')

        # 피크 탐색 및 표시
        if power_combined:
            peak_power_after_5h, peak_time_after_5h = -float('inf'), 0
            for t, p in zip(time_combined, power_combined):
                if t > 5.0 and p > peak_power_after_5h:
                    peak_power_after_5h, peak_time_after_5h = p, t

            # 그래프에 피크 지점 표시
            if peak_time_after_5h > 0:
                # 1. 빨간색 점 찍기
                ax.plot(peak_time_after_5h, peak_power_after_5h, 'ro', markersize=8)

                # 2. 정보 텍스트 박스 추가
                annotation_text = f'최대 피크 (5H 이후)\n시간: {peak_time_after_5h:.2f}H\n전력: {peak_power_after_5h:.2f}kW'
                ax.annotate(annotation_text,
                            xy=(peak_time_after_5h, peak_power_after_5h),
                            xytext=(peak_time_after_5h - 4, peak_power_after_5h),
                            fontsize=12, ha='center', va='top',
                            bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                            arrowprops=dict(facecolor='red', shrink=0.05, width=2))

        # ★★★★★ 축 범위 설정 수정 ★★★★★
        ax.set_title(f'저장된 레시피 비교 및 종합 전력 분석 ({repetition_count}회 반복)', fontsize=18)
        ax.set_xlabel('총 경과 시간 (H)')
        ax.set_ylabel('전력 (kW)')
        ax.axhline(0, color='black', linestyle='-', linewidth=0.8)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.legend()
        ax.set_xlim(left=0)  # 오른쪽(right) 제한을 제거하여 자동으로 전체 시간 표시

        st.pyplot(fig)

        # --- 5. 피크 정보 요약 출력 ---
        if power_combined:
            st.markdown("---")
            st.subheader("종합 전력 분석 결과")
            overall_peak_power = max(power_combined)

            col1, col2 = st.columns(2)
            with col1:
                st.metric("전체 기간 최대 피크 (kW)", f"{overall_peak_power:.2f}")
            with col2:
                if peak_time_after_5h > 0:
                    st.metric("최대 피크 (5H 이후)", f"{peak_power_after_5h:.2f} kW", delta=f"{peak_time_after_5h:.2f} H 시점")