"""Логіка каталогу «НРК-Координатор» без залежності від Streamlit."""
from __future__ import annotations

import json
import math
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "robots.json"

TASK_OPTIONS = [
    "Логістика",
    "Евакуація",
    "Інженерні роботи",
    "Спостереження",
    "Розвідка",
    "Бойове застосування",
    "Спеціальні завдання",
    "Зв’язок/ретрансляція",
    "Носій БпЛА",
    "Мінування",
]
CHASSIS_OPTIONS = ["Гусеничне", "Колісне"]

# Початкові значення каталогу призначені для роботи з прототипом.
# Перевіряй їх за першоджерелами перед використанням у дослідницькому тексті.
DEFAULT_ROBOTS: list[dict[str, Any]] = [
    {"name": "Varkhan", "tasks": ["Логістика", "Евакуація"], "payload_kg": 300, "range_km": 40, "autonomy_hours": 5, "chassis": "Колісне"},
    {"name": "Vepr (Вепр)", "tasks": ["Логістика", "Евакуація", "Інженерні роботи"], "payload_kg": 350, "range_km": 40, "autonomy_hours": 5, "chassis": "Гусеничне"},
    {"name": "NEO-1", "tasks": ["Інженерні роботи", "Логістика"], "payload_kg": 70, "range_km": 25, "autonomy_hours": 8, "chassis": "Колісне"},
    {"name": "Бізон-Л", "tasks": ["Логістика", "Евакуація", "Інженерні роботи", "Спеціальні завдання", "Зв’язок/ретрансляція", "Мінування"], "payload_kg": 300, "range_km": 50, "autonomy_hours": 6, "chassis": "Гусеничне"},
    {"name": "TerMIT", "tasks": ["Логістика", "Евакуація", "Інженерні роботи", "Розвідка", "Бойове застосування"], "payload_kg": 300, "range_km": 20, "autonomy_hours": 12, "chassis": "Гусеничне"},
    {"name": "PROTECTOR", "tasks": ["Логістика", "Евакуація", "Спеціальні завдання"], "payload_kg": 700, "range_km": 400, "autonomy_hours": 10, "chassis": "Колісне"},
    {"name": "Zmiy Droid 12.7", "tasks": ["Розвідка", "Бойове застосування"], "payload_kg": 100, "range_km": 30, "autonomy_hours": 5, "chassis": "Колісне"},
    {"name": "Лють", "tasks": ["Бойове застосування", "Спеціальні завдання"], "payload_kg": 50, "range_km": 20, "autonomy_hours": 2, "chassis": "Колісне"},
    {"name": "Гном", "tasks": ["Логістика", "Евакуація", "Спостереження", "Розвідка", "Спеціальні завдання", "Зв’язок/ретрансляція"], "payload_kg": 120, "range_km": 35, "autonomy_hours": 6, "chassis": "Колісне"},
    {"name": "Гном-Мінер", "tasks": ["Інженерні роботи"], "payload_kg": 41, "range_km": 33, "autonomy_hours": 5, "chassis": "Колісне"},
    {"name": "Примара-Killer", "tasks": ["Бойове застосування", "Евакуація"], "payload_kg": 150, "range_km": 25, "autonomy_hours": 4, "chassis": "Гусеничне"},
    {"name": "Плющ+", "tasks": ["Спостереження", "Розвідка", "Спеціальні завдання", "Зв’язок/ретрансляція"], "payload_kg": 60, "range_km": 40, "autonomy_hours": 6, "chassis": "Колісне"},
    {"name": "Ratel X", "tasks": ["Логістика", "Спостереження", "Розвідка", "Спеціальні завдання", "Носій БпЛА"], "payload_kg": 400, "range_km": 100, "autonomy_hours": 8, "chassis": "Колісне"},
]

# Поширені альтернативні написання, що допомагають доповнювати вже наявні записи.
MODEL_ALIASES: dict[str, tuple[str, ...]] = {
    "varkhan": ("varkhan", "вархан"),
    "vepr (вепр)": ("vepr", "вепр", "vepr вепр"),
    "neo-1": ("neo 1", "neo-1"),
    "бізон-л": ("бізон л", "bizon-l", "bizon l"),
    "termit": ("терміт",),
    "protector": (),
    "zmiy droid 12.7": ("змій дроїд 12 7", "змій droid 12 7"),
    "лють": ("liut", "lyut"),
    "гном": (),
    "гном-мінер": ("гном мінер", "гном-минер", "gnom-miner", "gnom miner"),
    "примара-killer": ("примара killer", "примара-killer"),
    "плющ+": ("плющ", "плющ плюс"),
    "ratel x": ("рател х", "рател x"),
}

# Точні назви тестових/помилково внесених записів, які слід прибрати.
_EXCLUDED_ALIASES = {"даша", "dasha", "доманська", "доманская", "domanska", "л", "l"}


def _name_key(name: Any) -> str:
    raw = str(name or "").strip().casefold()
    raw = re.sub(r"^нрк[\s\-–—.:]*", "", raw)
    raw = raw.replace("ё", "е")
    raw = re.sub(r"[^a-zа-яіїєґ0-9+]+", " ", raw, flags=re.IGNORECASE)
    return " ".join(raw.split())


def _default_for_name(name: str) -> dict[str, Any] | None:
    target = _name_key(name)
    for robot in DEFAULT_ROBOTS:
        candidates = {_name_key(robot["name"])}
        for alias in MODEL_ALIASES.get(robot["name"].casefold(), ()):
            candidates.add(_name_key(alias))
        # Some canonical English labels need an explicit key mapping.
        if robot["name"] == "Vepr (Вепр)":
            candidates.update({_name_key("vepr"), _name_key("вепр")})
        if target in candidates:
            return robot
    # Alias table may use a normalized Ukrainian key while the display label contains Latin letters.
    for canonical_key, aliases in MODEL_ALIASES.items():
        if target == _name_key(canonical_key) or target in {_name_key(a) for a in aliases}:
            for robot in DEFAULT_ROBOTS:
                if _name_key(robot["name"]) == _name_key(canonical_key):
                    return robot
    return None


def is_excluded_name(name: Any) -> bool:
    """Excludes only exact mistaken names; does not remove «Бізон-Л» or «Лють»."""
    key = _name_key(name)
    return not key or key in {_name_key(x) for x in _EXCLUDED_ALIASES}

def as_optional_number(value: Any) -> int | float | None:
    """Повертає додатне числове значення або None, якщо його не задано/воно некоректне."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, str):
        # Міграція старого каталогу: прибираємо позначку '*' з числових значень,
        # зберігаючи саме число. Позначки умовності не показуються в інтерфейсі.
        value = value.strip().rstrip("*＊✱").strip().replace(",", ".")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return int(number) if number.is_integer() else number



def parse_numeric_fields(raw_fields: dict[str, Any], limits: dict[str, int | float]) -> tuple[dict[str, int | float | None], list[str]]:
    """Розбирає введені текстом числа та повертає значення й перелік помилок."""
    parsed: dict[str, int | float | None] = {}
    errors: list[str] = []
    for label, raw in raw_fields.items():
        text = str(raw or "").strip()
        if not text:
            parsed[label] = None
            continue
        value = as_optional_number(text)
        if value is None:
            errors.append(f"Поле «{label}» має містити додатне число або бути порожнім.")
            continue
        if value > limits[label]:
            errors.append(f"Значення поля «{label}» не може перевищувати {limits[label]}.")
            continue
        parsed[label] = value
    return parsed, errors


def normalize_chassis(value: Any) -> str | None:
    """Залишає лише підтримувані значення типу шасі."""
    if not value:
        return None
    text = str(value).strip().casefold()
    if "гусен" in text or "tracked" in text:
        return "Гусеничне"
    if "коліс" in text or "колес" in text or "wheeled" in text or "4x4" in text or "6x6" in text or "8x8" in text:
        return "Колісне"
    return None


def _enrich_known_model(robot: dict[str, Any]) -> dict[str, Any]:
    """Completes known models from the local catalogue template without overwriting existing values."""
    default = _default_for_name(robot["name"])
    if not default:
        return robot

    existing_tasks = list(robot.get("tasks") or [])
    if not existing_tasks:
        robot["tasks"] = list(default.get("tasks", []))
    else:
        for task in default.get("tasks", []):
            if task not in existing_tasks:
                existing_tasks.append(task)
        robot["tasks"] = existing_tasks

    for field in ("payload_kg", "range_km", "autonomy_hours", "chassis"):
        if robot.get(field) in (None, "") and default.get(field) not in (None, ""):
            robot[field] = default[field]
    return robot

def normalize_robot(row: Any) -> dict[str, Any] | None:
    """Перевіряє та приводить запис до поточної структури каталогу."""
    if not isinstance(row, dict):
        return None

    name = str(row.get("name") or row.get("Назва") or "").strip()
    if not name or is_excluded_name(name):
        return None
    if name.casefold().startswith(("нрк-демо-", "демо-", "демо ", "demo-", "demo ")):
        return None

    raw_tasks = row.get("tasks", row.get("Призначення", []))
    if isinstance(raw_tasks, str):
        raw_tasks = [part.strip() for part in raw_tasks.split(",") if part.strip()]
    if not isinstance(raw_tasks, list):
        raw_tasks = []
    tasks: list[str] = []
    for task in raw_tasks:
        clean_task = str(task).strip()
        if clean_task in TASK_OPTIONS and clean_task not in tasks:
            tasks.append(clean_task)

    payload = row.get("payload_kg", row.get("Вантажопідйомність (кг)", row.get("Вантажопідйомність, кг")))
    distance = row.get("range_km", row.get("Запас ходу (км)", row.get("Запас ходу, км")))
    autonomy = row.get("autonomy_hours", row.get("Автономність (год)", row.get("Автономність, год")))
    if autonomy is None and row.get("Автономність, хв") not in (None, ""):
        try:
            autonomy = float(row["Автономність, хв"]) / 60
        except (TypeError, ValueError):
            autonomy = None

    chassis = row.get("chassis", row.get("Тип шасі", row.get("Тип бази")))
    normalized = {
        "name": name,
        "tasks": tasks,
        "payload_kg": as_optional_number(payload),
        "range_km": as_optional_number(distance),
        "autonomy_hours": as_optional_number(autonomy),
        "chassis": normalize_chassis(chassis),
    }
    return _enrich_known_model(normalized)


def normalize_catalog(rows: Any) -> list[dict[str, Any]]:
    """Нормалізує список та прибирає тестові записи й повтори назв."""
    if not isinstance(rows, list):
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        item = normalize_robot(row)
        if item is None:
            continue
        key = item["name"].casefold()
        if key not in seen:
            seen.add(key)
            normalized.append(item)
    return normalized



def save_catalog(items: list[dict[str, Any]], path: Path | str = DATA_FILE) -> None:
    """Атомарно зберігає каталог, щоб зменшити ризик пошкодження JSON-файлу."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_catalog(items)
    temporary = target.with_suffix(target.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(normalized, file, ensure_ascii=False, indent=2)
        file.write("\n")
    temporary.replace(target)


def _backup_file(path: Path, label: str = "backup") -> Path | None:
    """Робить резервну копію JSON перед міграцією або відновленням."""
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.stem}.{label}-{stamp}{path.suffix}")
    try:
        shutil.copy2(path, backup)
        return backup
    except OSError:
        return None


def load_catalog(path: Path | str = DATA_FILE) -> tuple[list[dict[str, Any]], str | None]:
    """Завантажує каталог; порожній список залишається порожнім."""
    target = Path(path)
    if not target.exists():
        defaults = normalize_catalog(DEFAULT_ROBOTS)
        save_catalog(defaults, target)
        return defaults, None

    try:
        with target.open("r", encoding="utf-8") as file:
            saved = json.load(file)
        if not isinstance(saved, list):
            raise ValueError("JSON має містити список записів")
    except (json.JSONDecodeError, OSError, ValueError):
        backup = _backup_file(target, "backup-broken")
        defaults = normalize_catalog(DEFAULT_ROBOTS)
        warning = "Файл каталогу не вдалося прочитати."
        if backup:
            warning += f" Створено резервну копію: {backup.name}."
        try:
            save_catalog(defaults, target)
            warning += " Завантажено початковий набір моделей; перевір каталог перед використанням."
        except OSError:
            warning += " Початкові дані завантажено лише в пам’ять; збереження недоступне."
        return defaults, warning

    normalized = normalize_catalog(saved)
    if normalized != saved:
        # Перед автоматичним прибиранням тестових/дублікатних записів робимо резервну копію.
        backup = _backup_file(target, "backup-before-cleanup")
        try:
            save_catalog(normalized, target)
        except OSError:
            message = "Каталог прочитано, але не вдалося зберегти оновлений формат."
            if backup:
                message += f" Резервна копія: {backup.name}."
            return normalized, message
    return normalized, None


def display_value(value: Any) -> Any:
    """Показує відсутні характеристики тире."""
    return "—" if value is None or value == "" else value



def catalog_row(robot: dict[str, Any]) -> dict[str, Any]:
    return {
        "Назва": robot.get("name", ""),
        "Призначення": ", ".join(robot.get("tasks", [])) or "—",
        "Вантажопідйомність (кг)": display_value(robot.get("payload_kg")),
        "Запас ходу (км)": display_value(robot.get("range_km")),
        "Автономність (год)": display_value(robot.get("autonomy_hours")),
        "Тип шасі": display_value(robot.get("chassis")),
    }


def matches_criteria(robot: dict[str, Any], criteria: dict[str, Any]) -> bool:
    """Перевіряє відповідність усім заданим критеріям; невідоме значення не є підтвердженим збігом."""
    required_task = criteria.get("task")
    if required_task and required_task not in robot.get("tasks", []):
        return False

    required_chassis = criteria.get("chassis")
    if required_chassis and required_chassis != "Усі типи":
        if robot.get("chassis") != required_chassis:
            return False

    numeric_pairs = (
        ("min_payload", "payload_kg"),
        ("min_range", "range_km"),
        ("min_autonomy", "autonomy_hours"),
    )
    for criteria_key, robot_key in numeric_pairs:
        threshold = as_optional_number(criteria.get(criteria_key))
        if threshold is None:
            continue
        actual = as_optional_number(robot.get(robot_key))
        if actual is None or actual < threshold:
            return False
    return True
