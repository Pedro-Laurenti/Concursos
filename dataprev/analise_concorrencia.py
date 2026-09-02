"""
Analisa concorrência DATAPREV 2026 a partir do PDF de homologação de inscrições.
Extrai todos os candidatos e gera estatísticas por perfil e local de prova.

Uso:
    python analise_concorrencia.py

Dependências:
    pip install pypdf

Ajuste VAGAS e VAGAS_RESERVA conforme o edital oficial antes de rodar.
"""
import re, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from collections import Counter
from multiprocessing import Pool, cpu_count

PDF_PATH      = r"C:\Users\p.laurenti.de.matos\Desktop\DEVP\Concursos\dataprev\concurso-dataprev-resultado-preliminar-de-homologacao.pdf"
MEU_PERFIL    = "Desenvolvimento de Software"
MEU_LOCAL     = "Florianópolis/SC"
VAGAS         = 20  # vagas efetivas para Florianópolis/SC neste perfil
VAGAS_RESERVA = 80  # cadastro de reserva

OUTPUT_TXT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultado_concorrencia.txt")

PERFIS = [
    "Desenvolvimento de Software",
    "Inteligência da Informação",
    "Análise de Negócio de TI",
    "Gestão de Serviços de TIC",
    "Segurança Cibernética e Proteção de Dados",
    "Arquitetura, Engenharia e Sustentação Tecnológica",
    "Administração e Governança",
    "Gestão Econômico-Financeira",
    "Comunicação Social",
    "Advocacia",
    "Engenharia",
]

# Ordena do mais longo pro mais curto para evitar match parcial
PERFIS_SORTED = sorted(PERFIS, key=len, reverse=True)


def parse_page(args):
    page_num, text = args
    results = []
    if not text:
        return results
    for line in text.split("\n"):
        line = line.strip()
        m = re.match(r'^(\d{12})\s+(.+)$', line)
        if not m:
            continue
        inscricao = m.group(1)
        rest = m.group(2).strip()
        for p in PERFIS_SORTED:
            if p in rest:
                idx = rest.index(p)
                nome  = rest[:idx].strip()
                local = rest[idx + len(p):].strip()
                if nome:
                    results.append((inscricao, nome, p, local))
                break
    return results


class Tee:
    """Escreve simultaneamente no terminal e num arquivo."""
    def __init__(self, filepath):
        self.terminal = sys.stdout
        self.file = open(filepath, 'w', encoding='utf-8')

    def write(self, msg):
        self.terminal.write(msg)
        self.file.write(msg)

    def flush(self):
        self.terminal.flush()
        self.file.flush()

    def close(self):
        self.file.close()


def main():
    from pypdf import PdfReader

    tee = Tee(OUTPUT_TXT)
    sys.stdout = tee

    try:
        print("Abrindo PDF...")
        reader = PdfReader(PDF_PATH)
        total  = len(reader.pages)
        print(f"Páginas: {total} — extraindo texto...")

        pages_text = []
        for i, page in enumerate(reader.pages):
            if i % 200 == 0:
                print(f"  Lendo página {i+1}/{total}...")
            pages_text.append((i, page.extract_text() or ""))

        print("Analisando candidatos...")
        all_candidates = []
        cores = min(cpu_count(), 8)
        with Pool(cores) as pool:
            for chunk in pool.map(parse_page, pages_text, chunksize=50):
                all_candidates.extend(chunk)

        print(f"\nTotal candidatos homologados: {len(all_candidates):,}\n")

        # ── Por perfil ──────────────────────────────────────────────────────
        perfil_count = Counter(c[2] for c in all_candidates)
        print("CANDIDATOS POR PERFIL:")
        for perfil, cnt in perfil_count.most_common():
            tag = "  <-- SEU PERFIL" if perfil == MEU_PERFIL else ""
            print(f"  {cnt:6,}  {perfil}{tag}")

        # ── Meu perfil por cidade ───────────────────────────────────────────
        meu = [c for c in all_candidates if c[2] == MEU_PERFIL]
        locais = Counter(c[3] for c in meu)
        total_meu = sum(locais.values())
        print(f"\n{MEU_PERFIL} — {total_meu:,} candidatos por local de prova:")
        max_cnt = locais.most_common(1)[0][1]
        for local, cnt in locais.most_common():
            tag = "  <-- VOCE" if local == MEU_LOCAL else ""
            pct = cnt / total_meu * 100
            bar = "█" * min(35, round(cnt * 35 / max_cnt))
            print(f"  {cnt:5,}  {bar:<35}  {pct:5.1f}%  {local}{tag}")

        # ── Foco Florianópolis ──────────────────────────────────────────────
        flori = [c for c in meu if c[3] == MEU_LOCAL]
        total_vagas = VAGAS + VAGAS_RESERVA
        print(f"\nSUA CONCORRÊNCIA — {MEU_LOCAL} / {MEU_PERFIL}:")
        print(f"  Candidatos inscritos   : {len(flori):,}")
        print(f"  Vagas efetivas         : {VAGAS}")
        print(f"  Cadastro de reserva    : {VAGAS_RESERVA}")
        print(f"  Total vagas + reserva  : {total_vagas}")
        print(f"  Relação cand/vaga (ef.): {len(flori)/VAGAS:.0f}:1")
        print(f"  Relação cand/vaga (+CR): {len(flori)/total_vagas:.0f}:1")
        pct_flori = len(flori) / total_meu * 100
        print(f"  % do total do perfil   : {pct_flori:.1f}% dos candidatos de {MEU_PERFIL}")

        print(f"\n  Lista completa de candidatos em {MEU_LOCAL} (ordem alfabética):")
        for i, c in enumerate(sorted(flori, key=lambda x: x[1]), 1):
            print(f"  {i:3}. {c[0]}  {c[1]}")

    finally:
        sys.stdout = tee.terminal
        tee.close()
        print(f"\nResultado salvo em: {OUTPUT_TXT}")


if __name__ == "__main__":
    main()
