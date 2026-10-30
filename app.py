"""Інтерфейс Streamlit для каталогу «НРК-Координатор»."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from nrk_core import (
    CHASSIS_OPTIONS,
    DATA_FILE,
    TASK_OPTIONS,
    as_optional_number,
    catalog_row,
    load_catalog,
    matches_criteria,
    normalize_catalog,
    parse_numeric_fields,
    save_catalog,
)

st.set_page_config(page_title="НРК-Координатор", page_icon="🤖", layout="wide")

if "robots" not in st.session_state:
    loaded, warning = load_catalog(DATA_FILE)
    st.session_state.robots = loaded
    st.session_state.catalog_warning = warning
    st.session_state.save_error = None
else:
    normalized = normalize_catalog(st.session_state.robots)
    if normalized != st.session_state.robots:
        st.session_state.robots = normalized


def persist_catalog() -> bool:
    try:
        save_catalog(st.session_state.robots, DATA_FILE)
        st.session_state.save_error = None
        return True
    except OSError as exc:
        st.session_state.save_error = str(exc)
        return False


def numeric_text(label: str, initial: int | float | None, *, key: str, placeholder: str = "Не зазначено") -> str:
    """Текстове поле для чисел: дозволяє вводити з клавіатури й залишати порожнім."""
    value = "" if initial is None else str(initial)
    return st.text_input(label, value=value, placeholder=placeholder, key=key,
                         help="Введи додатне число або залиш поле порожнім, якщо значення невідоме.")



st.title("🤖 НРК-Координатор")
st.write("Каталог українських наземних роботизованих комплексів")
if st.session_state.get("catalog_warning"):
    st.warning(st.session_state.catalog_warning)
if st.session_state.get("save_error"):
    st.error(f"Не вдалося зберегти каталог: {st.session_state.save_error}")

# ---------- Бічна панель: керування каталогом ----------
robots: list[dict] = st.session_state.robots
with st.sidebar.expander("➕ Додати НРК", expanded=False):
    with st.form("add_robot_form", clear_on_submit=True):
        new_name = st.text_input("Назва моделі", key="new_name")
        new_tasks = st.multiselect("Призначення", TASK_OPTIONS, key="new_tasks")
        new_payload = numeric_text("Вантажопідйомність (кг)", None, key="new_payload")
        new_range = numeric_text("Запас ходу (км)", None, key="new_range")
        new_autonomy = numeric_text("Автономність (год)", None, key="new_autonomy")
        new_chassis = st.selectbox("Тип шасі", CHASSIS_OPTIONS, index=None, placeholder="Не зазначено", key="new_chassis")
        add_submitted = st.form_submit_button("Додати до каталогу")

    if add_submitted:
        clean_name = new_name.strip()
        parsed, errors = parse_numeric_fields({
            "Вантажопідйомність (кг)": new_payload,
            "Запас ходу (км)": new_range,
            "Автономність (год)": new_autonomy,
        }, {"Вантажопідйомність (кг)": 10000, "Запас ходу (км)": 2000, "Автономність (год)": 1000})
        if not clean_name:
            errors.append("Укажи назву моделі.")
        if not new_tasks:
            errors.append("Обери щонайменше одне призначення.")
        if any(row["name"].casefold() == clean_name.casefold() for row in robots):
            errors.append("Запис із такою назвою вже існує. Скористайся редагуванням.")
        if errors:
            for message in errors:
                st.error(message)
        else:
            robots.append({
                "name": clean_name,
                "tasks": new_tasks,
                "payload_kg": parsed["Вантажопідйомність (кг)"],
                "range_km": parsed["Запас ходу (км)"],
                "autonomy_hours": parsed["Автономність (год)"],
                "chassis": new_chassis,
            })
            if persist_catalog():
                st.success("Запис додано та збережено.")
                st.rerun()

with st.sidebar.expander("✏️ Редагувати НРК", expanded=False):
    if not robots:
        st.info("Каталог порожній — спочатку додай запис.")
    else:
        edit_name_choice = st.selectbox("Вибери модель для редагування", [r["name"] for r in robots], key="edit_name_choice")
        edit_row = next(r for r in robots if r["name"] == edit_name_choice)
        suffix = edit_name_choice
        with st.form("edit_robot_form"):
            edit_name = st.text_input("Назва моделі", value=edit_row["name"], key=f"edit_name_{suffix}")
            edit_tasks = st.multiselect("Призначення", TASK_OPTIONS, default=edit_row.get("tasks", []), key=f"edit_tasks_{suffix}")
            edit_payload = numeric_text("Вантажопідйомність (кг)", edit_row.get("payload_kg"), key=f"edit_payload_{suffix}")
            edit_range = numeric_text("Запас ходу (км)", edit_row.get("range_km"), key=f"edit_range_{suffix}")
            edit_autonomy = numeric_text("Автономність (год)", edit_row.get("autonomy_hours"), key=f"edit_autonomy_{suffix}")
            chassis_index = CHASSIS_OPTIONS.index(edit_row["chassis"]) if edit_row.get("chassis") in CHASSIS_OPTIONS else None
            edit_chassis = st.selectbox("Тип шасі", CHASSIS_OPTIONS, index=chassis_index, placeholder="Не зазначено", key=f"edit_chassis_{suffix}")
            edit_submitted = st.form_submit_button("Зберегти зміни")

        if edit_submitted:
            clean_edit_name = edit_name.strip()
            parsed, errors = parse_numeric_fields({
                "Вантажопідйомність (кг)": edit_payload,
                "Запас ходу (км)": edit_range,
                "Автономність (год)": edit_autonomy,
            }, {"Вантажопідйомність (кг)": 10000, "Запас ходу (км)": 2000, "Автономність (год)": 1000})
            if not clean_edit_name:
                errors.append("Назва не може бути порожньою.")
            if not edit_tasks:
                errors.append("Обери щонайменше одне призначення.")
            if any(r["name"].casefold() == clean_edit_name.casefold() and r is not edit_row for r in robots):
                errors.append("Інший запис уже має таку назву.")
            if errors:
                for message in errors:
                    st.error(message)
            else:
                edited_values = {
                    "name": clean_edit_name,
                    "tasks": edit_tasks,
                    "payload_kg": parsed["Вантажопідйомність (кг)"],
                    "range_km": parsed["Запас ходу (км)"],
                    "autonomy_hours": parsed["Автономність (год)"],
                    "chassis": edit_chassis,
                }
                edit_row.update(edited_values)
                if persist_catalog():
                    st.success("Зміни збережено.")
                    st.rerun()

with st.sidebar.expander("🗑️ Видалити НРК", expanded=False):
    if not robots:
        st.info("Каталог порожній.")
    else:
        delete_name = st.selectbox("Вибери модель для видалення", [r["name"] for r in robots], key="delete_name_choice")
        confirm_delete = st.checkbox(f"Підтверджую видалення запису «{delete_name}»", key=f"confirm_delete_{delete_name}")
        if st.button("Видалити вибраний запис", key="delete_robot_button"):
            if not confirm_delete:
                st.error("Постав галочку підтвердження перед видаленням.")
            else:
                st.session_state.robots = [r for r in robots if r["name"] != delete_name]
                if persist_catalog():
                    st.success(f"Запис «{delete_name}» видалено з каталогу.")
                    st.rerun()

# ---------- 1. Каталог ----------
robots = st.session_state.robots
st.subheader("1. Каталог українських НРК")
metric_a, metric_b, metric_c, metric_d = st.columns(4)
metric_a.metric("Моделей у каталозі", len(robots))
metric_b.metric("Колісні", sum(r.get("chassis") == "Колісне" for r in robots))
metric_c.metric("Гусеничні", sum(r.get("chassis") == "Гусеничне" for r in robots))
metric_d.metric("Типів завдань", len({task for r in robots for task in r.get("tasks", [])}))

filter1, filter2, filter3 = st.columns([2, 1, 1])
search_name = filter1.text_input("Пошук за назвою", placeholder="Введи назву НРК", key="catalog_search")
task_filter = filter2.selectbox("Призначення", ["Усі завдання", *TASK_OPTIONS], key="catalog_task_filter")
chassis_filter = filter3.selectbox("Тип шасі", ["Усі типи", *CHASSIS_OPTIONS], key="catalog_chassis_filter")
visible_robots = []
for robot in robots:
    if search_name.strip() and search_name.strip().casefold() not in robot.get("name", "").casefold():
        continue
    if task_filter != "Усі завдання" and task_filter not in robot.get("tasks", []):
        continue
    if chassis_filter != "Усі типи" and robot.get("chassis") != chassis_filter:
        continue
    visible_robots.append(robot)

columns = ["Назва", "Призначення", "Вантажопідйомність (кг)", "Запас ходу (км)", "Автономність (год)", "Тип шасі"]
catalog_df = pd.DataFrame([catalog_row(r) for r in visible_robots], columns=columns)
if catalog_df.empty:
    st.info("За вибраними фільтрами записів немає." if robots else "Каталог порожній. Додай перший запис через меню зліва.")
else:
    st.dataframe(catalog_df, use_container_width=True, hide_index=True)
st.caption(f"Показано записів: {len(visible_robots)} із {len(robots)}. Тире — характеристику не внесено.")

# ---------- 2. Критерії добору ----------
st.subheader("2. Критерії добору")
criterion_a, criterion_b = st.columns(2)
task_type = criterion_a.selectbox("Тип завдання", TASK_OPTIONS, index=0, key="criterion_task")
required_chassis = criterion_b.selectbox("Тип шасі", ["Усі типи", *CHASSIS_OPTIONS], index=0, key="criterion_chassis")
criterion_c, criterion_d, criterion_e = st.columns(3)
required_payload = criterion_c.number_input("Мінімальна вантажопідйомність (кг)", min_value=0, max_value=10000, value=0, step=10, help="0 — не використовувати критерій.", key="criterion_payload")
required_range = criterion_d.number_input("Мінімальний запас ходу (км)", min_value=0, max_value=2000, value=0, step=5, help="0 — не використовувати критерій.", key="criterion_range")
required_autonomy = criterion_e.number_input("Мінімальна автономність (год)", min_value=0, max_value=1000, value=0, step=1, help="0 — не використовувати критерій.", key="criterion_autonomy")

# ---------- 3. Результат ----------
st.subheader("3. Результат добору")
criteria = {
    "task": task_type,
    "min_payload": required_payload,
    "min_range": required_range,
    "min_autonomy": required_autonomy,
    "chassis": required_chassis,
}
st.write(
    f"**Завдання:** {task_type}  ·  **Вантажопідйомність від:** {required_payload or 'без обмеження'} кг  ·  "
    f"**Запас ходу від:** {required_range or 'без обмеження'} км  ·  "
    f"**Автономність від:** {required_autonomy or 'без обмеження'} год  ·  **Шасі:** {required_chassis}"
)
matched_robots = [r for r in robots if matches_criteria(r, criteria)]
result_df = pd.DataFrame([catalog_row(r) for r in matched_robots], columns=columns)
if matched_robots:
    st.success(f"Знайдено НРК, що відповідають заданим критеріям: {len(matched_robots)}.")
    st.dataframe(result_df, use_container_width=True, hide_index=True)
else:
    st.error("За заданими критеріями відповідних НРК не знайдено.")
    if not robots:
        st.caption("Спочатку додай записи до каталогу.")
