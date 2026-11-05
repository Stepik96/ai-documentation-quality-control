"""Real Codex analysis of synthetic examples; never writes to GitHub."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))
from test_controller import fixture
import controller as c


def main():
    policy, snapshot, _ = fixture()
    policy["mode"] = "dry-run"
    policy["allowed_authors"] = ["developer"]
    results = []
    for case in ("correct_docs", "data_isolation_bug", "fixed_data_isolation"):
        s = copy.deepcopy(snapshot)
        s["pr"]["title"] = "Контролируемый локальный пример " + case
        s["documents_from_base"] = {
            "README.md": "V1 — замечания, одна компания, личная история. Исправленная копия — план V2. Приложение пока разрабатывается.",
            "docs/developers/scope.md": "Действующие сценарии данного локального примера: V1 — план проверки документов и замечаний с личной историей. V2 — план исправленной копии. Реализации приложения пока нет. История включает только записи текущего аутентифицированного пользователя. В примере current_user достоверно установлен внешним слоем аутентификации. Других действующих нормативных документов нет."
        }
        s["head"] = ("a" if case == "correct_docs" else "c" if case == "data_isolation_bug" else "d") * 40
        s["pr"]["head"]["sha"] = s["head"]
        if case == "correct_docs":
            source = "# Руководство\nV1 планируется для проверки документов и выдачи замечаний.\nИсправленная копия планируется в V2. Реализации приложения пока нет.\n"
            path = "docs/guide.md"
            requirement = "Уточнить в руководстве, что замечания планируются в V1, исправленная копия в V2; не представлять функции как готовые"
        else:
            path = "src/history.py"
            source = ("def history(current_user, records):\n    return records\n" if case == "data_isolation_bug" else
                      "def history(current_user, records):\n    return [r for r in records if r['owner_id'] == current_user['id']]\n")
            requirement = "history возвращает только записи текущего пользователя, чужие записи исключены; current_user проверен слоем аутентификации"
        s["files"] = [{"filename": path, "status": "added", "patch": "@@ -0,0 +1," + str(len(source.splitlines())) + " @@\n" + "\n".join("+" + l for l in source.splitlines())}]
        s["head_contents"] = {path: source}
        s["criteria"] = [{"id": "3:1", "requirement": requirement}]
        s["issues"] = [{"number": 3, "body": "## Критерии готовности\n- [ ] " + requirement}]
        result = c.codex_analyze(s, results[-1]["result"] if case == "fixed_data_isolation" else None, policy)
        decision, reasons = c.decide(s, result, policy)
        artifact = {"case": case, "result": result, "decision": decision, "reasons": reasons}
        results.append(artifact)
        c.write_json(c.ROOT / ".state" / "smoke" / (case + ".json"), artifact)
        print(case + ": " + decision, flush=True)
    if results[0]["decision"] != "APPROVE" or results[1]["decision"] != "REQUEST_CHANGES" or results[2]["decision"] == "REQUEST_CHANGES":
        raise c.Stop("Real model smoke-test did not meet expected outcomes; human inspection required")
    print("Local real-model smoke completed. No GitHub publication or merge occurred.")


if __name__ == "__main__":
    main()
