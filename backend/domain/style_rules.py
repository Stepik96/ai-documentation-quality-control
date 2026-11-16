from backend.domain.check import Finding

TABLE_FONT_POINTS = 10
TABLE_FONT_HALF_POINTS = TABLE_FONT_POINTS * 2
SYSTEM_OBJECTS = ("Планирование деятельности предприятия",)


def table_font_finding(location: str, size: int) -> Finding:
    points = f"{size / 2:g}"
    return Finding(
        location,
        "R02",
        f"Размер текста в таблицах — {TABLE_FONT_POINTS} пт.",
        f"Размер текста в ячейке — {points} пт.",
        f"Установите размер {TABLE_FONT_POINTS} пт для указанного текста.",
        "Оформление Word",
    )


def table_reference_finding(location: str, number: str) -> Finding:
    return Finding(
        location,
        "R03",
        "На каждую подписанную таблицу должна быть ссылка в основном тексте.",
        f"В основном тексте не найдена ссылка на таблицу {number}.",
        f"Добавьте ссылку, например «см. таблицу {number}».",
    )


def object_bold_finding(location: str, name: str) -> Finding:
    return Finding(
        location,
        "R01",
        "Названия объектов системы выделяются полужирным.",
        f"Название «{name}» выделено полужирным не целиком.",
        "Примените полужирное начертание ко всему названию.",
        "Оформление Word",
    )
