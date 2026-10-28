import re
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import app as nida


class ApoioPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_db = nida.DB
        self.previous_secret = nida.app.secret_key
        nida.DB = str(Path(self.temp_dir.name) / "apoio-test.db")
        nida.app.secret_key = "test-secret-for-support-module"
        nida.app.config["TESTING"] = True
        nida.iniciar_banco()
        with nida.app.app_context():
            self.owner_id = nida.criar_usuaria(nida.db(), "owner@example.test", "password123", "Owner")
            self.other_id = nida.criar_usuaria(nida.db(), "other@example.test", "password123", "Other")
            for user_id in (self.owner_id, self.other_id):
                nida.db().execute("UPDATE paciente SET data_inicio=? WHERE usuario_id=?",
                                  (date.today().isoformat(), user_id))
            nida.db().commit()
        self.client = nida.app.test_client()

    def tearDown(self):
        nida.DB = self.previous_db
        nida.app.secret_key = self.previous_secret
        self.temp_dir.cleanup()

    def authenticate_as(self, user_id):
        with self.client.session_transaction() as session:
            session["uid"] = user_id

    def csrf_token(self):
        response = self.client.get("/apoio-emocional")
        self.assertEqual(response.status_code, 200)
        match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
        self.assertIsNotNone(match)
        return match.group(1)

    def test_support_page_requires_authentication(self):
        response = self.client.get("/apoio-emocional")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/entrar", response.headers["Location"])

    def test_private_diary_is_owner_scoped_and_escaped_in_html(self):
        self.authenticate_as(self.owner_id)
        token = self.csrf_token()
        response = self.client.post("/apoio-emocional", data={
            "csrf_token": token,
            "tipo": "diario",
            "data": date.today().isoformat(),
            "nota": "<script>nao executar</script>",
        })
        self.assertEqual(response.status_code, 302)
        with nida.app.app_context():
            record = nida.db().execute(
                "SELECT usuario_id, nivel, nota FROM humor WHERE usuario_id=? ORDER BY id DESC LIMIT 1",
                (self.owner_id,),
            ).fetchone()
            self.assertEqual(record["usuario_id"], self.owner_id)
            self.assertIsNone(record["nivel"])
            self.assertEqual(record["nota"], "<script>nao executar</script>")

        page = self.client.get("/apoio-emocional").get_data(as_text=True)
        self.assertIn('id="dias-calendario"', page)
        self.assertNotIn("<script>nao executar</script>", page)
        month = self.client.get(f"/apoio-emocional/diario?mes={date.today().strftime('%Y-%m')}")
        self.assertEqual(month.get_json()["registros"][0]["nota"], "<script>nao executar</script>")
        self.authenticate_as(self.other_id)
        other_month = self.client.get(f"/apoio-emocional/diario?mes={date.today().strftime('%Y-%m')}")
        self.assertNotIn("nao executar", str(other_month.get_json()))

    def test_diary_post_requires_csrf_token(self):
        self.authenticate_as(self.owner_id)
        response = self.client.post("/apoio-emocional", data={
            "tipo": "diario",
            "nota": "Um registro privado",
        })
        self.assertEqual(response.status_code, 400)
        with nida.app.app_context():
            count = nida.db().execute("SELECT COUNT(*) FROM humor WHERE usuario_id=?", (self.owner_id,)).fetchone()[0]
            self.assertEqual(count, 0)

    def test_owner_cannot_delete_another_users_record(self):
        with nida.app.app_context():
            cursor = nida.db().execute(
                "INSERT INTO humor (usuario_id, data, nivel, nota) VALUES (?,?,NULL,?)",
                (self.other_id, date.today().isoformat(), "Registro da outra conta"),
            )
            other_record_id = cursor.lastrowid
            nida.db().commit()

        self.authenticate_as(self.owner_id)
        token = self.csrf_token()
        response = self.client.post(
            f"/apoio-emocional/registros/{other_record_id}/excluir",
            data={"csrf_token": token},
        )
        self.assertEqual(response.status_code, 404)
        with nida.app.app_context():
            record = nida.db().execute("SELECT usuario_id FROM humor WHERE id=?", (other_record_id,)).fetchone()
            self.assertEqual(record["usuario_id"], self.other_id)

    def test_owner_can_delete_their_record(self):
        self.authenticate_as(self.owner_id)
        token = self.csrf_token()
        response = self.client.post("/apoio-emocional", data={
            "csrf_token": token,
            "tipo": "diario",
            "data": date.today().isoformat(),
            "nota": "Apagar este registro",
        })
        self.assertEqual(response.status_code, 302)
        with nida.app.app_context():
            record_id = nida.db().execute(
                "SELECT id FROM humor WHERE usuario_id=? ORDER BY id DESC LIMIT 1", (self.owner_id,)
            ).fetchone()["id"]

        response = self.client.post(
            f"/apoio-emocional/registros/{record_id}/excluir",
            data={"csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)
        with nida.app.app_context():
            remaining = nida.db().execute("SELECT 1 FROM humor WHERE id=?", (record_id,)).fetchone()
            self.assertIsNone(remaining)

    def test_invalid_mood_value_is_rejected(self):
        self.authenticate_as(self.owner_id)
        token = self.csrf_token()
        response = self.client.post("/apoio-emocional", data={
            "csrf_token": token,
            "tipo": "humor",
            "nivel": "9",
        })
        self.assertEqual(response.status_code, 400)
        with nida.app.app_context():
            count = nida.db().execute("SELECT COUNT(*) FROM humor WHERE usuario_id=?", (self.owner_id,)).fetchone()[0]
            self.assertEqual(count, 0)

    def test_diary_entry_can_be_saved_for_a_past_calendar_day(self):
        self.authenticate_as(self.owner_id)
        token = self.csrf_token()
        entry_date = date.today().replace(day=1).isoformat()
        response = self.client.post("/apoio-emocional", data={
            "csrf_token": token,
            "tipo": "diario",
            "data": entry_date,
            "nota": "Lembrei de uma conversa importante.",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"diario=1", response.headers["Location"])
        self.assertIn(f"data={entry_date}", response.headers["Location"])
        with nida.app.app_context():
            record = nida.db().execute(
                "SELECT data, nota FROM humor WHERE usuario_id=? ORDER BY id DESC LIMIT 1",
                (self.owner_id,),
            ).fetchone()
            self.assertEqual(record["data"], entry_date)
            self.assertEqual(record["nota"], "Lembrei de uma conversa importante.")

    def test_future_diary_date_is_rejected(self):
        self.authenticate_as(self.owner_id)
        token = self.csrf_token()
        future_date = date.today() + timedelta(days=1)
        response = self.client.post("/apoio-emocional", data={
            "csrf_token": token,
            "tipo": "diario",
            "data": future_date.isoformat(),
            "nota": "Registro futuro",
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("Escolha uma data válida", response.get_data(as_text=True))
        with nida.app.app_context():
            count = nida.db().execute("SELECT COUNT(*) FROM humor WHERE usuario_id=?", (self.owner_id,)).fetchone()[0]
            self.assertEqual(count, 0)

    def test_calendar_api_returns_only_owner_records_for_requested_month(self):
        owner_date = date.today().replace(day=1).isoformat()
        with nida.app.app_context():
            nida.db().execute(
                "INSERT INTO humor (usuario_id, data, nivel, nota) VALUES (?,?,NULL,?)",
                (self.owner_id, owner_date, "Registro do mês"),
            )
            nida.db().execute(
                "INSERT INTO humor (usuario_id, data, nivel, nota) VALUES (?,?,NULL,?)",
                (self.other_id, owner_date, "Não pode aparecer"),
            )
            nida.db().commit()
        self.authenticate_as(self.owner_id)
        response = self.client.get(f"/apoio-emocional/diario?mes={owner_date[:7]}")
        self.assertEqual(response.status_code, 200)
        records = response.get_json()["registros"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["nota"], "Registro do mês")

    def test_diary_search_finds_private_notes(self):
        with nida.app.app_context():
            nida.db().execute(
                "INSERT INTO humor (usuario_id, data, nivel, nota) VALUES (?,?,NULL,?)",
                (self.owner_id, date.today().isoformat(), "Uma conversa de esperança"),
            )
            nida.db().commit()
        self.authenticate_as(self.owner_id)
        response = self.client.get(
            f"/apoio-emocional/diario?mes={date.today().strftime('%Y-%m')}&q=ESPERAN%C3%87A"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["registros"][0]["nota"], "Uma conversa de esperança")

    def test_invalid_calendar_month_is_rejected(self):
        self.authenticate_as(self.owner_id)
        response = self.client.get("/apoio-emocional/diario?mes=2026-13")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
