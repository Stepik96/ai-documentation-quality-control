export type Scenario = "findings" | "clean" | "partial" | "error";

export type Category = "Оформление" | "Структура" | "Язык";

export type Finding = {
  id: string;
  category: Category;
  location: string;
  ruleId: string;
  rule: string;
  title: string;
  problem: string;
  recommendation: string;
  quote?: string;
};

export type DemoReport = {
  scenario: Scenario;
  completeness: "complete" | "partial";
  findings: Finding[];
  unchecked: string[];
  rulesVersion: string;
  fileName: string;
  createdAt: string;
  source: string;
};

export const SCENARIOS: {
  id: Scenario;
  label: string;
  description: string;
}[] = [
  {
    id: "findings",
    label: "Есть замечания",
    description: "Пять примеров замечаний к оформлению, структуре и языку.",
  },
  {
    id: "clean",
    label: "Без замечаний",
    description: "Пример завершённой проверки без замечаний.",
  },
  {
    id: "partial",
    label: "Частичный результат",
    description: "Оформление и структура проверены; проверка языка недоступна.",
  },
  {
    id: "error",
    label: "Ошибка проверки",
    description: "Не удалось показать пример результата.",
  },
];

// Fictional fixtures for the interface, not the result of reading a user's file.
// Candidate rules cover different document types in a sample style guide.
// They are not an approved rule set.
const EXAMPLE_FINDINGS: Finding[] = [
  {
    id: "paragraphjustify",
    category: "Оформление",
    location: "Страница 2 · абзац 3",
    ruleId: "paragraphjustify",
    rule: "Кандидат правила: выравнивание основного текста по ширине.",
    title: "Выравнивание основного текста",
    problem: "В этом примере абзац основного текста выровнен по левому краю.",
    recommendation:
      "Задайте абзацу выравнивание по ширине согласно образцу руководства.",
    quote:
      "В данном разделе описан порядок настройки рабочего места пользователя.",
  },
  {
    id: "imperative",
    category: "Язык",
    location: "Страница 3 · раздел «Настройка»",
    ruleId: "imperative",
    rule: "Кандидат правила: безличные формулировки вместо повелительного наклонения.",
    title: "Повелительное наклонение",
    problem: "В примере используется повелительное наклонение.",
    recommendation:
      "Используйте безличную формулировку: «Следует открыть раздел Администрирование».",
    quote: "Откройте раздел «Администрирование».",
  },
  {
    id: "tableheader",
    category: "Структура",
    location: "Страница 4 · таблица 1",
    ruleId: "tableheader",
    rule: "Кандидат правила для ЧТЗ и ПР: у таблицы должна быть шапка.",
    title: "Добавьте шапку таблицы",
    problem: "У таблицы в примере отсутствует строка с названиями столбцов.",
    recommendation:
      "Добавьте шапку, например «Параметр», «Значение» и «Описание».",
  },
  {
    id: "tablereference",
    category: "Структура",
    location: "Страница 4 · таблица 1",
    ruleId: "tablereference",
    rule: "Кандидат правила для ЧТЗ и ПР: текст должен содержать ссылку на таблицу.",
    title: "Укажите ссылку на таблицу в тексте",
    problem: "В тексте примера нет ссылки на таблицу.",
    recommendation:
      "Добавьте фразу со ссылкой, например «Параметры настройки приведены в таблице 1».",
  },
  {
    id: "systemobjectsboldonlyguides",
    category: "Оформление",
    location: "Страница 3 · раздел «Настройка»",
    ruleId: "systemobjectsboldonlyguides",
    rule: "Кандидат правила для руководств пользователя: названия объектов системы выделяются полужирным без кавычек.",
    title: "Название объекта: полужирное, без кавычек",
    problem:
      "В примере руководства название элемента интерфейса заключено в кавычки и не выделено полужирным.",
    recommendation:
      "Уберите кавычки и выделите название раздела Администрирование полужирным. В образце это правило относится к руководствам пользователя.",
    quote: "Следует открыть раздел «Администрирование».",
  },
];

export function createDemoReport(
  scenario: Scenario,
  fileName: string,
): DemoReport {
  const findings =
    scenario === "findings"
      ? EXAMPLE_FINDINGS
      : scenario === "partial"
        ? EXAMPLE_FINDINGS.filter((finding) => finding.category !== "Язык")
        : [];

  return {
    scenario,
    completeness:
      scenario === "partial" || scenario === "error" ? "partial" : "complete",
    findings: findings.map((finding) => ({ ...finding })),
    unchecked:
      scenario === "partial"
        ? ["Язык: формулировки инструкций не проверены."]
        : scenario === "error"
          ? ["Оформление, структура и язык: проверка не выполнена."]
          : [],
    rulesVersion: "demo-1",
    fileName,
    createdAt: new Date().toISOString(),
    source:
      "Синтетические примеры для разных типов проектных документов. Не утверждённые правила. Содержимое выбранного файла не анализируется.",
  };
}

export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) {
    return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 }).format(bytes / 1024)} КБ`;
  }
  if (bytes < 1024 * 1024 * 1024) {
    return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 }).format(bytes / (1024 * 1024))} МБ`;
  }
  return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 }).format(bytes / (1024 * 1024 * 1024))} ГБ`;
}

export function getSelectionError(files: FileList | File[]): string | null {
  if (files.length === 0) return "Выберите один документ для проверки.";
  if (files.length > 1)
    return "Можно проверить один документ за раз. Выберите один файл.";
  return null;
}
