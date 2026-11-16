import { useEffect, useRef, useState } from "react";
import type { DragEvent } from "react";
import {
  AlignJustify,
  ArrowDownLeft,
  ArrowUpRight,
  Check,
  CheckCheck,
  ChevronRight,
  CircleAlert,
  Copy,
  FileText,
  Info,
  ListTree,
  LoaderCircle,
  Plus,
  RotateCcw,
  ScanLine,
  ShieldCheck,
  TextCursorInput,
  X,
} from "lucide-react";
import {
  createDemoReport,
  formatFileSize,
  getSelectionError,
  SCENARIOS,
} from "./demo";
import type { DemoReport, Finding, Scenario } from "./demo";
import { CheckSubmissionError, uploadDocument } from "./api/checks";
import "./App.css";

const EXAMPLE_FILE = "Пример проектной документации.docx";
const UPLOAD_TIMEOUT_MS = 30_000;

type Submission =
  | { state: "idle" }
  | { state: "submitting" }
  | { state: "accepted"; checkId: string }
  | { state: "error"; message: string };

function DocumentArtwork({ selected = false }: { selected?: boolean }) {
  return (
    <div
      className={`document-artwork ${selected ? "is-selected" : ""}`}
      aria-hidden="true"
    >
      <div className="artwork-orbit" />
      <div className="paper-shadow paper-shadow-back" />
      <div className="paper-shadow" />
      <div className="paper-sheet">
        <div className="paper-top">
          <span className="paper-mark" />
          <span>DOC / 01</span>
        </div>
        <div className="paper-title">
          ПРОЕКТНАЯ
          <br />
          ДОКУМЕНТАЦИЯ
        </div>
        <div className="paper-lines">
          <i />
          <i />
          <i />
        </div>
        <div className="paper-table">
          <i />
          <i />
          <i />
          <i />
          <i />
          <i />
        </div>
        <div className="paper-bottom">
          <span>01—05</span>
          <CheckCheck size={16} />
        </div>
      </div>
      <div className="artwork-stamp">
        <ScanLine size={18} />
        <span>{selected ? "ВЫБРАН" : "DOC"}</span>
      </div>
    </div>
  );
}

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [selectionError, setSelectionError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [screen, setScreen] = useState<"upload" | "report">("upload");
  const [scenario, setScenario] = useState<Scenario>("findings");
  const [report, setReport] = useState<DemoReport | null>(null);
  const [activeId, setActiveId] = useState("");
  const [copied, setCopied] = useState(false);
  const [copyMessage, setCopyMessage] = useState("");
  const [submission, setSubmission] = useState<Submission>({ state: "idle" });
  const inputRef = useRef<HTMLInputElement>(null);
  const chooseRef = useRef<HTMLButtonElement>(null);
  const workspaceRef = useRef<HTMLElement>(null);
  const reportHeadingRef = useRef<HTMLHeadingElement>(null);
  const detailRef = useRef<HTMLElement>(null);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const uploadRef = useRef<AbortController | null>(null);
  useEffect(
    () => () => {
      if (copyTimer.current) clearTimeout(copyTimer.current);
      const pendingUpload = uploadRef.current;
      uploadRef.current = null;
      pendingUpload?.abort();
    },
    [],
  );
  useEffect(() => {
    const preventFileNavigation = (event: globalThis.DragEvent) => {
      if (Array.from(event.dataTransfer?.types ?? []).includes("Files"))
        event.preventDefault();
      if (event.type === "drop") setDragging(false);
    };
    window.addEventListener("dragover", preventFileNavigation);
    window.addEventListener("drop", preventFileNavigation);
    return () => {
      window.removeEventListener("dragover", preventFileNavigation);
      window.removeEventListener("drop", preventFileNavigation);
    };
  }, []);

  function selectFile(files: FileList | File[] | null) {
    if (uploadRef.current) return;
    if (!files || !files.length) return;
    const error = getSelectionError(files);
    if (error) {
      setSelectionError(error);
      return;
    }
    setFile(files[0]);
    setSelectionError("");
    setSubmission({ state: "idle" });
    requestAnimationFrame(() =>
      chooseRef.current?.focus({ preventScroll: true }),
    );
  }
  function dropFile(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    selectFile(event.dataTransfer.files);
  }
  async function submitDocument() {
    if (!file || uploadRef.current || submission.state === "accepted") return;
    const controller = new AbortController();
    uploadRef.current = controller;
    setSubmission({ state: "submitting" });
    setSelectionError("");
    setDragging(false);
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, UPLOAD_TIMEOUT_MS);
    try {
      const accepted = await uploadDocument(file, controller.signal);
      if (uploadRef.current === controller)
        setSubmission({ state: "accepted", checkId: accepted.checkId });
    } catch (error) {
      if (uploadRef.current !== controller) return;
      setSubmission({
        state: "error",
        message: timedOut
          ? "Сервер не ответил вовремя. Приём документа не подтверждён. Попробуйте отправить файл ещё раз."
          : error instanceof CheckSubmissionError
            ? error.message
            : "Не удалось отправить документ. Проверьте соединение и повторите попытку.",
      });
    } finally {
      clearTimeout(timer);
      if (uploadRef.current === controller) uploadRef.current = null;
    }
  }
  function showReport(
    nextScenario: Scenario,
    fileName = report?.fileName ?? EXAMPLE_FILE,
    focusHeading = true,
  ) {
    const next = createDemoReport(nextScenario, fileName);
    setScenario(nextScenario);
    setReport(next);
    setActiveId(next.findings[0]?.id ?? "");
    setCopied(false);
    setCopyMessage("");
    setScreen("report");
    requestAnimationFrame(() => {
      workspaceRef.current?.scrollIntoView({
        block: "start",
        behavior: "instant",
      });
      if (focusHeading)
        reportHeadingRef.current?.focus({ preventScroll: true });
    });
  }
  function newCheck(goToTop = false) {
    const pendingUpload = uploadRef.current;
    uploadRef.current = null;
    pendingUpload?.abort();
    setSubmission({ state: "idle" });
    setScreen("upload");
    setReport(null);
    setFile(null);
    setSelectionError("");
    setScenario("findings");
    setCopied(false);
    requestAnimationFrame(() => {
      if (goToTop) window.scrollTo({ top: 0, behavior: "instant" });
      else
        workspaceRef.current?.scrollIntoView({
          block: "start",
          behavior: "instant",
        });
      chooseRef.current?.focus({ preventScroll: true });
    });
  }
  function selectFinding(finding: Finding) {
    setActiveId(finding.id);
    setCopied(false);
    setCopyMessage("");
    if (window.matchMedia("(max-width: 760px)").matches)
      requestAnimationFrame(() => detailRef.current?.focus());
  }
  async function copyFinding(finding: Finding) {
    const text = `${finding.title}\nМесто: ${finding.location}\nЧто обнаружено: ${finding.problem}\nПравило: ${finding.rule}\nКак исправить: ${finding.recommendation}\nДемонстрационный пример, а не результат анализа файла.`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setCopyMessage("Замечание скопировано");
      if (copyTimer.current) clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopyMessage(
        "Браузер не разрешил копирование. Можно выделить текст замечания вручную.",
      );
    }
  }
  const activeFinding = report?.findings.find(
    (finding) => finding.id === activeId,
  );
  const isReport = screen === "report" && report !== null;
  const isSubmitting = submission.state === "submitting";
  const isAccepted = submission.state === "accepted";

  return (
    <div className={`app ${isReport ? "has-report" : ""}`}>
      <a className="skip-link" href="#workspace">
        Перейти к проверке документа
      </a>
      <header className="site-header">
        <a
          className="brand"
          href="#"
          onClick={(event) => {
            event.preventDefault();
            newCheck(true);
          }}
          aria-label="докчек — на главную"
        >
          <span className="brand-symbol" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>
          <span>
            докчек<span className="brand-period">.</span>
          </span>
        </a>
        <nav className="header-nav" aria-label="Основная навигация">
          <a href="#workspace">Проверка</a>
        </nav>
        <button
          className="button button-header"
          onClick={() => showReport("findings", EXAMPLE_FILE)}
        >
          Пример отчёта <ArrowUpRight size={16} />
        </button>
      </header>
      <main>
        <section className="hero" aria-labelledby="hero-title">
          <h1 id="hero-title">Контроль проектной документации</h1>
          <p>
            Оформление, структура и язык — понятные замечания и рекомендации в
            одном отчёте.
          </p>
        </section>
        <div className="workspace-surround">
          <div className="rail rail-left" aria-hidden="true">
            <i />
            <span>DOCUMENT / REVIEW</span>
          </div>
          <div className="rail rail-right" aria-hidden="true">
            <i />
          </div>
          <section
            id="workspace"
            className="workspace"
            ref={workspaceRef}
            aria-label="Проверка документа"
          >
            <div className="window-chrome">
              <span className="window-dots" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
              <span>
                {isReport
                  ? "Отчёт / демонстрационные данные"
                  : "Новая проверка"}
              </span>
              <span className="demo-label">
                <span />
                {isReport ? "Демо" : "Загрузка"}
              </span>
            </div>
            {!isReport ? (
              <div className="upload-layout appear">
                <div className="upload-intro">
                  <span className="eyebrow">01 / Ваш документ</span>
                  <h2>
                    Начнём{" "}
                    <br />с документа.
                  </h2>
                  <p>
                    Выберите готовый файл.
                    <br /> Отправьте документ и получите подтверждение, что он
                    принят в очередь на проверку.
                  </p>
                  <div className="scope-list" aria-label="Направления проверки">
                    <span>
                      <AlignJustify size={16} />
                      Оформление
                    </span>
                    <span>
                      <ListTree size={16} />
                      Структура
                    </span>
                    <span>
                      <TextCursorInput size={16} />
                      Язык
                    </span>
                  </div>
                  <button
                    className="text-button example-link"
                    onClick={() => showReport("findings", EXAMPLE_FILE)}
                  >
                    Посмотреть пример отчёта <ArrowUpRight size={16} />
                  </button>
                </div>
                <div className="upload-control">
                  <input
                    ref={inputRef}
                    type="file"
                    disabled={isSubmitting}
                    className="visually-hidden"
                    tabIndex={-1}
                    aria-label="Выбрать один документ"
                    onChange={(event) => {
                      selectFile(event.target.files);
                      event.target.value = "";
                    }}
                  />
                  <div
                    className={`dropzone ${dragging ? "is-dragging" : ""} ${file ? "has-file" : ""}`}
                    onDragOver={(event) => {
                      event.preventDefault();
                      if (!isSubmitting) setDragging(true);
                    }}
                    onDragLeave={(event) => {
                      if (
                        !(event.relatedTarget instanceof Node) ||
                        !event.currentTarget.contains(event.relatedTarget)
                      )
                        setDragging(false);
                    }}
                    onDrop={dropFile}
                  >
                    <span
                      className="dropzone-corner corner-tl"
                      aria-hidden="true"
                    />
                    <span
                      className="dropzone-corner corner-tr"
                      aria-hidden="true"
                    />
                    <span
                      className="dropzone-corner corner-bl"
                      aria-hidden="true"
                    />
                    <span
                      className="dropzone-corner corner-br"
                      aria-hidden="true"
                    />
                    <DocumentArtwork selected={!!file} />
                    {file ? (
                      <div className="selected-file" aria-live="polite">
                        <span className="file-state">
                          <Check size={12} />
                          Документ выбран
                        </span>
                        <h3>{file.name}</h3>
                        <div className="file-metadata">
                          {formatFileSize(file.size)}
                          <span>·</span>Один файл
                        </div>
                        <div className="file-actions">
                          <button
                            className="text-button"
                            ref={chooseRef}
                            disabled={isSubmitting}
                            onClick={() => inputRef.current?.click()}
                          >
                            <RotateCcw size={13} />
                            Заменить
                          </button>
                          <button
                            className="text-button"
                            disabled={isSubmitting}
                            onClick={() => {
                              setFile(null);
                              setSelectionError("");
                              setSubmission({ state: "idle" });
                              requestAnimationFrame(() =>
                                chooseRef.current?.focus(),
                              );
                            }}
                          >
                            <X size={13} />
                            Убрать
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="empty-file">
                        <h3>Перетащите документ сюда</h3>
                        <p>или выберите один файл на компьютере</p>
                        <button
                          className="button button-file"
                          ref={chooseRef}
                          onClick={() => inputRef.current?.click()}
                        >
                          <Plus size={15} />
                          Выбрать файл
                        </button>
                      </div>
                    )}
                  </div>
                  {selectionError && (
                    <div className="selection-error" role="alert">
                      <CircleAlert size={15} />
                      {selectionError}
                    </div>
                  )}
                  <div className="upload-action-row">
                    <span className="file-count">
                      <span className={file ? "is-ready" : ""} />
                      {isSubmitting
                        ? "Отправляем документ"
                        : isAccepted
                          ? "В очереди на проверку"
                          : file
                            ? "Готов к отправке"
                            : "Ожидаем документ"}
                    </span>
                    <button
                      className="button button-primary check-button"
                      disabled={!file || isSubmitting || isAccepted}
                      aria-busy={isSubmitting}
                      onClick={submitDocument}
                    >
                      {isSubmitting ? (
                        <>
                          Отправляем{" "}
                          <LoaderCircle className="upload-spinner" size={17} />
                        </>
                      ) : isAccepted ? (
                        <>
                          Принято <Check size={17} />
                        </>
                      ) : (
                        <>
                          Проверить <ArrowUpRight size={17} />
                        </>
                      )}
                    </button>
                  </div>
                  <div
                    className="submission-feedback"
                    aria-live="polite"
                    aria-atomic="true"
                  >
                    {isSubmitting && (
                      <p className="upload-progress">
                        Идёт отправка файла. Дождитесь ответа сервера.
                      </p>
                    )}
                    {submission.state === "accepted" && (
                      <div className="upload-accepted" role="status">
                        <CheckCheck size={19} />
                        <div>
                          <strong>Документ принят, ожидает проверки</strong>
                          <p>
                            Номер заявки:{" "}
                            <span className="accepted-id">
                              {submission.checkId}
                            </span>
                          </p>
                          <p>
                            Статус и результат появятся на следующих этапах
                            разработки.
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                  {submission.state === "error" && (
                    <div className="selection-error upload-error" role="alert">
                      <CircleAlert size={17} />
                      <div>
                        <strong>Приём документа не подтверждён</strong>
                        <p>{submission.message}</p>
                      </div>
                    </div>
                  )}
                  <p className="demo-disclosure">
                    <Info size={14} />
                    <span>
                      По нажатию «Проверить» файл отправится на сервер. «Пример
                      отчёта» показывает отдельные демонстрационные данные.
                    </span>
                  </p>
                </div>
              </div>
            ) : (
              <div className="report-layout appear">
                <div className="report-topline">
                  <span className="eyebrow">02 / Результат</span>
                  <button className="text-button" onClick={() => newCheck()}>
                    <Plus size={15} />
                    Новый документ
                  </button>
                </div>
                <div className="report-header">
                  <div>
                    <h2 ref={reportHeadingRef} tabIndex={-1}>
                      Пример отчёта<span className="title-period">.</span>
                    </h2>
                    <p className="report-filename">
                      <FileText size={14} />
                      <span>{report.fileName}</span>
                    </p>
                  </div>
                  <label className="scenario-control">
                    <span>Сценарий демо</span>
                    <select
                      value={scenario}
                      onChange={(event) =>
                        showReport(
                          event.target.value as Scenario,
                          report.fileName,
                          false,
                        )
                      }
                    >
                      {SCENARIOS.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="report-demo-note">
                  <Info size={15} />
                  <p>
                    Это демонстрационные данные. Содержимое выбранного файла не
                    анализировалось.
                  </p>
                </div>
                {scenario === "error" ? (
                  <div className="report-state error-state" role="alert">
                    <span className="state-symbol">
                      <CircleAlert size={27} />
                    </span>
                    <span className="eyebrow">Сценарий сбоя</span>
                    <h3>
                      Не удалось показать
                      <br />
                      пример результата.
                    </h3>
                    <p>
                      Это демонстрация состояния ошибки.
                      <br />
                      Можно повторить попытку или выбрать другой сценарий.
                    </p>
                    <button
                      className="button button-primary"
                      onClick={() => showReport("findings")}
                    >
                      <RotateCcw size={16} />
                      Повторить демонстрацию
                    </button>
                  </div>
                ) : (
                  <>
                    {report.completeness === "partial" && (
                      <div className="partial-notice" role="status">
                        <CircleAlert size={18} />
                        <div>
                          <strong>Частичный результат</strong>
                          <p>
                            {report.unchecked.join(" ")} Ноль замечаний не
                            означает, что документ проверен целиком.
                          </p>
                        </div>
                      </div>
                    )}
                    {report.findings.length === 0 ? (
                      <div className="report-state clean-state">
                        <span className="state-symbol">
                          <CheckCheck size={28} />
                        </span>
                        <span className="eyebrow">Завершённый пример</span>
                        <h3>
                          В этом примере
                          <br />
                          замечаний нет.
                        </h3>
                        <p>
                          Так выглядит отчёт без найденных нарушений.
                          <br />
                          Это не оценка загруженного вами документа.
                        </p>
                        <button
                          className="button button-outline"
                          onClick={() => showReport("findings")}
                        >
                          Посмотреть замечания <ArrowUpRight size={16} />
                        </button>
                      </div>
                    ) : (
                      <div className="findings-grid">
                        <div
                          className="findings-list"
                          aria-label="Список демонстрационных замечаний"
                        >
                          <div className="findings-list-label">
                            <span>Замечания</span>
                            <span>
                              {String(report.findings.length).padStart(2, "0")}
                            </span>
                          </div>
                          {report.findings.map((finding, index) => (
                            <button
                              className={`finding-item ${activeId === finding.id ? "is-active" : ""}`}
                              aria-pressed={activeId === finding.id}
                              key={finding.id}
                              onClick={() => selectFinding(finding)}
                            >
                              <span className="finding-number">
                                {String(index + 1).padStart(2, "0")}
                              </span>
                              <span className="finding-summary">
                                <span
                                  className={`category category-${finding.category === "Язык" ? "language" : finding.category === "Структура" ? "structure" : "format"}`}
                                >
                                  {finding.category}
                                </span>
                                <strong>{finding.title}</strong>
                                <small>{finding.location}</small>
                              </span>
                              <ChevronRight size={15} />
                            </button>
                          ))}
                        </div>
                        {activeFinding && (
                          <article
                            className="finding-detail"
                            ref={detailRef}
                            tabIndex={-1}
                            aria-label={`Подробности: ${activeFinding.title}`}
                          >
                            <div className="detail-topline">
                              <span className="eyebrow">
                                Замечание{" "}
                                {String(
                                  report.findings.indexOf(activeFinding) + 1,
                                ).padStart(2, "0")}
                              </span>
                              <span className="rule-tag">
                                {report.rulesVersion}
                              </span>
                            </div>
                            <h3>{activeFinding.title}</h3>
                            <p className="detail-location">
                              <FileText size={14} />
                              {activeFinding.location}
                            </p>
                            <dl className="detail-fields">
                              <div>
                                <dt>Что обнаружено</dt>
                                <dd>{activeFinding.problem}</dd>
                              </div>
                              {activeFinding.quote && (
                                <div className="quote-field">
                                  <dt>Фрагмент примера</dt>
                                  <dd>{activeFinding.quote}</dd>
                                </div>
                              )}
                              <div>
                                <dt>Правило</dt>
                                <dd>{activeFinding.rule}</dd>
                              </div>
                              <div className="recommendation-field">
                                <dt>
                                  <ArrowDownLeft size={14} />
                                  Как исправить
                                </dt>
                                <dd>{activeFinding.recommendation}</dd>
                              </div>
                            </dl>
                            <div className="detail-bottom">
                              <span>Правки — в вашем редакторе</span>
                              <button
                                className="text-button"
                                onClick={() => copyFinding(activeFinding)}
                              >
                                {copied ? (
                                  <Check size={14} />
                                ) : (
                                  <Copy size={14} />
                                )}
                                {copied ? "Скопировано" : "Копировать"}
                              </button>
                            </div>
                            <p className="copy-feedback" aria-live="polite">
                              {copyMessage}
                            </p>
                          </article>
                        )}
                      </div>
                    )}
                    <div className="report-footnote">
                      <ShieldCheck size={14} />
                      <p>
                        Правила и замечания синтетические, для демонстрации
                        интерфейса. Они не являются утверждённым стандартом
                        компании.
                      </p>
                    </div>
                  </>
                )}
              </div>
            )}
            <div className="workspace-footer">
              <span>
                <ShieldCheck size={13} />
                {isReport
                  ? "Демонстрационный отчёт не анализирует ваш файл"
                  : "Файл передаётся только после нажатия «Проверить»"}
              </span>
            </div>
          </section>
        </div>
      </main>
      <footer className="site-footer">
        <a className="brand footer-brand" href="#" aria-label="докчек — наверх">
          <span className="brand-symbol" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>
          <span>докчек.</span>
        </a>
        <p>
          Внимание к документам.
          <br />
          Уважение к вашему времени.
        </p>
        <span className="eyebrow">Фронтенд-прототип / 2026</span>
      </footer>
    </div>
  );
}

export default App;
