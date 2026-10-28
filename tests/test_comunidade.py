from html.parser import HTMLParser
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

import app as nida


class ApoioMarkupParser(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.resource_ancestors = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        resource = attributes.get("data-recurso")
        if resource:
            self.resource_ancestors[resource] = [item[1] for item in self.stack]
        if tag not in self.VOID_TAGS:
            self.stack.append((tag, attributes.get("id")))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                return


class ComunidadeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_db = nida.DB
        self.previous_community_db = nida.COMMUNITY_DB
        self.previous_secret = nida.app.secret_key
        self.previous_moderators = nida.app.config["COMMUNITY_MODERATOR_IDS"]
        self.previous_testing = nida.app.config.get("TESTING", False)
        nida.DB = str(Path(self.temp_dir.name) / "nida-test.db")
        nida.COMMUNITY_DB = str(Path(self.temp_dir.name) / "community-test.db")
        nida.app.secret_key = "test-secret-for-community"
        nida.app.config["COMMUNITY_MODERATOR_IDS"] = ""
        nida.app.config["TESTING"] = True
        nida.iniciar_banco()
        with nida.app.app_context():
            self.owner_id = nida.criar_usuaria(nida.db(), "owner@example.test", "password123", "Owner")
            self.other_id = nida.criar_usuaria(nida.db(), "other@example.test", "password123", "Other")
            self.moderator_id = nida.criar_usuaria(nida.db(), "mod@example.test", "password123", "Moderator")
            for user_id in (self.owner_id, self.other_id, self.moderator_id):
                nida.db().execute("UPDATE paciente SET data_inicio=? WHERE usuario_id=?",
                                  (date.today().isoformat(), user_id))
            nida.db().commit()
        self.client = nida.app.test_client()

    def tearDown(self):
        nida.DB = self.previous_db
        nida.COMMUNITY_DB = self.previous_community_db
        nida.app.secret_key = self.previous_secret
        nida.app.config["COMMUNITY_MODERATOR_IDS"] = self.previous_moderators
        nida.app.config["TESTING"] = self.previous_testing
        self.temp_dir.cleanup()

    def authenticate_as(self, user_id):
        with self.client.session_transaction() as session:
            session["uid"] = user_id

    def csrf_token(self):
        response = self.client.get("/apoio-emocional/comunidade")
        self.assertEqual(response.status_code, 200)
        match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
        self.assertIsNotNone(match)
        return match.group(1)

    def set_profile(self, user_id, pseudonym):
        self.authenticate_as(user_id)
        response = self.client.post(
            "/apoio-emocional/comunidade/perfil",
            data={"csrf_token": self.csrf_token(), "pseudonimo": pseudonym},
        )
        self.assertEqual(response.status_code, 302)

    def create_post(self, user_id, text="Meu relato sobre a espera"):
        self.authenticate_as(user_id)
        response = self.client.post(
            "/apoio-emocional/comunidade/publicacoes",
            data={
                "csrf_token": self.csrf_token(),
                "categoria": "incerteza",
                "texto": text,
            },
        )
        self.assertEqual(response.status_code, 302)
        with nida.app.app_context():
            return nida.community_db().execute(
                "SELECT id FROM publicacoes WHERE usuario_id=? ORDER BY id DESC LIMIT 1", (user_id,)
            ).fetchone()["id"]

    def test_community_requires_login_and_stays_out_of_main_menu(self):
        response = self.client.get("/apoio-emocional/comunidade")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/entrar", response.headers["Location"])
        self.authenticate_as(self.owner_id)
        page = self.client.get("/apoio-emocional").get_data(as_text=True)
        self.assertIn('data-abrir-comunidade', page)
        community_button = re.search(r'<button[^>]*data-abrir-comunidade[^>]*>', page)
        self.assertIsNotNone(community_button)
        self.assertNotIn('target="_blank"', community_button.group(0))

    def test_support_shortcuts_point_to_existing_resources(self):
        self.authenticate_as(self.owner_id)
        page = self.client.get("/apoio-emocional").get_data(as_text=True)
        parser = ApoioMarkupParser()
        parser.feed(page)
        buttons = re.findall(r'data-abrir-recurso="([^"]+)"', page)
        resources = re.findall(r'data-recurso="([^"]+)"', page)
        self.assertEqual(set(buttons), set(resources))
        self.assertEqual(len(resources), len(set(resources)))
        self.assertEqual(
            set(resources),
            {"respiracao", "diario", "acolhimento", "biblioteca", "autocuidado", "consulta", "ajuda"},
        )
        self.assertIn("communityUrl", page)
        self.assertIn('respirar: "respiracao"', page)
        self.assertIn('diario: "diario"', page)
        self.assertIn('consulta: "consulta"', page)
        self.assertIn('data-abrir-recurso="biblioteca"', page)
        self.assertTrue(all("painel-recurso" in ancestors for ancestors in parser.resource_ancestors.values()))

    def test_posts_are_visible_immediately_to_the_community_and_html_is_escaped(self):
        self.set_profile(self.owner_id, "Pessoa_Amiga")
        post_id = self.create_post(self.owner_id, "<script>alert(1)</script>")

        owner_page = self.client.get("/apoio-emocional/comunidade").get_data(as_text=True)
        self.assertIn("Publicar relato", owner_page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", owner_page)
        self.authenticate_as(self.other_id)
        other_page = self.client.get("/apoio-emocional/comunidade").get_data(as_text=True)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", other_page)
        self.assertNotIn("usuario_id", other_page)
        self.assertEqual(self.client.get("/apoio-emocional/comunidade/moderacao").status_code, 403)
        self.assertNotIn("<script>alert(1)</script>", other_page)
        with nida.app.app_context():
            state = nida.community_db().execute(
                "SELECT estado FROM publicacoes WHERE id=?", (post_id,)
            ).fetchone()["estado"]
            self.assertEqual(state, "aprovada")

    def test_existing_waiting_posts_and_comments_can_be_published_by_their_authors(self):
        self.set_profile(self.owner_id, "PessoaAutora")
        self.set_profile(self.other_id, "OutraPessoa")
        post_id = self.create_post(self.owner_id, "Relato que estava aguardando")
        with nida.app.app_context():
            nida.community_db().execute(
                "UPDATE publicacoes SET estado='pendente' WHERE id=?", (post_id,)
            )
            nida.community_db().commit()

        self.authenticate_as(self.owner_id)
        token = self.csrf_token()
        owner_page = self.client.get("/apoio-emocional/comunidade").get_data(as_text=True)
        self.assertIn("Publicar meu relato agora", owner_page)
        self.authenticate_as(self.other_id)
        other_page = self.client.get("/apoio-emocional/comunidade").get_data(as_text=True)
        self.assertNotIn("Relato que estava aguardando", other_page)
        response = self.client.post(
            f"/apoio-emocional/comunidade/publicacoes/{post_id}/publicar",
            data={"csrf_token": token},
        )
        self.assertEqual(response.status_code, 404)

        self.authenticate_as(self.owner_id)
        response = self.client.post(
            f"/apoio-emocional/comunidade/publicacoes/{post_id}/publicar",
            data={"csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)
        self.authenticate_as(self.other_id)
        self.assertIn(
            "Relato que estava aguardando",
            self.client.get("/apoio-emocional/comunidade").get_data(as_text=True),
        )

        with nida.app.app_context():
            cursor = nida.community_db().execute(
                "INSERT INTO comentarios (publicacao_id, usuario_id, texto, estado, criado_em) "
                "VALUES (?,?,?,'pendente',?)",
                (post_id, self.other_id, "Comentário antigo em espera", "2026-10-28T03:00:00"),
            )
            comment_id = cursor.lastrowid
            nida.community_db().commit()
        other_page = self.client.get("/apoio-emocional/comunidade").get_data(as_text=True)
        self.assertIn("Publicar meu comentário agora", other_page)
        response = self.client.post(
            f"/apoio-emocional/comunidade/comentarios/{comment_id}/publicar",
            data={"csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)
        self.authenticate_as(self.owner_id)
        self.assertIn(
            "Comentário antigo em espera",
            self.client.get("/apoio-emocional/comunidade").get_data(as_text=True),
        )

    def test_reactions_comments_and_private_reports(self):
        self.set_profile(self.owner_id, "PessoaAutora")
        post_id = self.create_post(self.owner_id)

        self.set_profile(self.other_id, "PessoaLeitora")
        self.authenticate_as(self.other_id)
        token = self.csrf_token()
        response = self.client.post(
            f"/apoio-emocional/comunidade/publicacoes/{post_id}/reacoes",
            data={"csrf_token": token, "tipo": "estou_aqui"},
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            "/apoio-emocional/comunidade/denuncias",
            data={"csrf_token": token, "tipo_alvo": "publicacao", "alvo_id": post_id, "motivo": "dados_pessoais"},
        )
        self.assertEqual(response.status_code, 302)
        with nida.app.app_context():
            report_count = nida.community_db().execute("SELECT COUNT(*) FROM denuncias").fetchone()[0]
            reaction_count = nida.community_db().execute("SELECT COUNT(*) FROM reacoes").fetchone()[0]
            self.assertEqual(report_count, 1)
            self.assertEqual(reaction_count, 1)
        self.assertEqual(self.client.get("/apoio-emocional/comunidade/moderacao").status_code, 403)

        self.authenticate_as(self.moderator_id)
        nida.app.config["COMMUNITY_MODERATOR_IDS"] = {self.moderator_id}
        queue = self.client.get("/apoio-emocional/comunidade/moderacao").get_data(as_text=True)
        self.assertIn("Dados pessoais expostos", queue)
        self.assertNotIn("PessoaLeitora", queue)

        self.authenticate_as(self.other_id)
        comment_response = self.client.post(
            f"/apoio-emocional/comunidade/publicacoes/{post_id}/comentarios",
            data={"csrf_token": token, "texto": "Obrigada por compartilhar."},
        )
        self.assertEqual(comment_response.status_code, 302)
        with nida.app.app_context():
            comment_id = nida.community_db().execute(
                "SELECT id FROM comentarios WHERE publicacao_id=?", (post_id,)
            ).fetchone()["id"]
            comment_state = nida.community_db().execute(
                "SELECT estado FROM comentarios WHERE id=?", (comment_id,)
            ).fetchone()["estado"]
            self.assertEqual(comment_state, "aprovado")
        self.authenticate_as(self.owner_id)
        feed = self.client.get("/apoio-emocional/comunidade").get_data(as_text=True)
        self.assertIn("Obrigada por compartilhar.", feed)

    def test_moderation_can_remove_live_content_and_checks_role(self):
        self.set_profile(self.owner_id, "PessoaAutora")
        post_id = self.create_post(self.owner_id, "Conteúdo publicado")
        self.authenticate_as(self.moderator_id)
        token = self.csrf_token()
        self.assertEqual(
            self.client.post(
                f"/apoio-emocional/comunidade/moderacao/publicacao/{post_id}",
                data={"csrf_token": token, "acao": "remover"},
            ).status_code,
            403,
        )
        nida.app.config["COMMUNITY_MODERATOR_IDS"] = {self.moderator_id}
        self.authenticate_as(self.moderator_id)
        token = self.csrf_token()
        response = self.client.post(
            f"/apoio-emocional/comunidade/moderacao/publicacao/{post_id}",
            data={"csrf_token": token, "acao": "remover"},
        )
        self.assertEqual(response.status_code, 302)
        with nida.app.app_context():
            row = nida.community_db().execute(
                "SELECT estado, texto FROM publicacoes WHERE id=?", (post_id,)
            ).fetchone()
            self.assertEqual(row["estado"], "removida")
            self.assertEqual(row["texto"], "")

    def test_owner_checks_prevent_identifier_tampering(self):
        self.set_profile(self.owner_id, "PessoaAutora")
        post_id = self.create_post(self.owner_id)
        self.authenticate_as(self.other_id)
        token = self.csrf_token()
        response = self.client.post(
            f"/apoio-emocional/comunidade/publicacoes/{post_id}/excluir",
            data={"csrf_token": token},
        )
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            "/apoio-emocional/comunidade/denuncias",
            data={
                "csrf_token": token,
                "tipo_alvo": "publicacao",
                "alvo_id": post_id + 1000,
                "motivo": "outro",
            },
        )
        self.assertEqual(response.status_code, 404)
        with nida.app.app_context():
            row = nida.community_db().execute(
                "SELECT usuario_id FROM publicacoes WHERE id=?", (post_id,)
            ).fetchone()
            self.assertEqual(row["usuario_id"], self.owner_id)

    def test_duplicate_report_attempts_are_rate_limited(self):
        self.set_profile(self.owner_id, "PessoaAutora")
        post_id = self.create_post(self.owner_id)
        self.authenticate_as(self.other_id)
        token = self.csrf_token()
        payload = {
            "csrf_token": token,
            "tipo_alvo": "publicacao",
            "alvo_id": post_id,
            "motivo": "outro",
        }
        for attempt in range(6):
            response = self.client.post("/apoio-emocional/comunidade/denuncias", data=payload)
            if attempt < 5:
                self.assertEqual(response.status_code, 302)
            else:
                self.assertEqual(response.status_code, 429)
        with nida.app.app_context():
            count = nida.community_db().execute(
                "SELECT COUNT(*) FROM denuncias WHERE denunciante_id=?", (self.other_id,)
            ).fetchone()[0]
            self.assertEqual(count, 1)

    def test_authorized_moderator_can_resolve_a_report_and_remove_content(self):
        self.set_profile(self.owner_id, "PessoaAutora")
        post_id = self.create_post(self.owner_id, "Conteúdo denunciado")
        self.authenticate_as(self.other_id)
        token = self.csrf_token()
        report_response = self.client.post(
            "/apoio-emocional/comunidade/denuncias",
            data={
                "csrf_token": token,
                "tipo_alvo": "publicacao",
                "alvo_id": post_id,
                "motivo": "orientacao_clinica",
            },
        )
        self.assertEqual(report_response.status_code, 302)
        with nida.app.app_context():
            report_id = nida.community_db().execute(
                "SELECT id FROM denuncias WHERE publicacao_id=?", (post_id,)
            ).fetchone()["id"]
        nida.app.config["COMMUNITY_MODERATOR_IDS"] = {self.moderator_id}
        self.authenticate_as(self.moderator_id)
        response = self.client.post(
            f"/apoio-emocional/comunidade/moderacao/denuncias/{report_id}",
            data={"csrf_token": token, "acao": "remover"},
        )
        self.assertEqual(response.status_code, 302)
        with nida.app.app_context():
            post = nida.community_db().execute(
                "SELECT estado, texto FROM publicacoes WHERE id=?", (post_id,)
            ).fetchone()
            report = nida.community_db().execute(
                "SELECT estado FROM denuncias WHERE id=?", (report_id,)
            ).fetchone()
            self.assertEqual((post["estado"], post["texto"]), ("removida", ""))
            self.assertEqual(report["estado"], "revisada")

    def test_profile_and_community_writes_require_csrf_and_validate_inputs(self):
        self.authenticate_as(self.owner_id)
        self.assertEqual(
            self.client.post(
                "/apoio-emocional/comunidade/perfil", data={"pseudonimo": "no-csrf"}
            ).status_code,
            400,
        )
        token = self.csrf_token()
        response = self.client.post(
            "/apoio-emocional/comunidade/perfil",
            data={"csrf_token": token, "pseudonimo": "x"},
        )
        self.assertIn("pseudonimo_invalido", response.headers["Location"])
        self.set_profile(self.owner_id, "PseudonimoOk")
        self.set_profile(self.other_id, "OutroNome")
        self.authenticate_as(self.other_id)
        response = self.client.post(
            "/apoio-emocional/comunidade/perfil",
            data={"csrf_token": self.csrf_token(), "pseudonimo": "PseudonimoOk"},
        )
        self.assertIn("pseudonimo_em_uso", response.headers["Location"])

    def test_community_post_rate_limit_is_enforced(self):
        self.set_profile(self.owner_id, "PessoaAutora")
        self.authenticate_as(self.owner_id)
        for index in range(5):
            response = self.client.post(
                "/apoio-emocional/comunidade/publicacoes",
                data={
                    "csrf_token": self.csrf_token(),
                    "categoria": "comecando",
                    "texto": f"Relato {index}",
                },
            )
            self.assertEqual(response.status_code, 302)
        response = self.client.post(
            "/apoio-emocional/comunidade/publicacoes",
            data={
                "csrf_token": self.csrf_token(),
                "categoria": "comecando",
                "texto": "Relato extra",
            },
        )
        self.assertEqual(response.status_code, 429)


if __name__ == "__main__":
    unittest.main()
