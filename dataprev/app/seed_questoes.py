"""
seed_questoes.py — importa questões de arquivos JSON direto para o Azure Table Storage

Uso:
  python seed_questoes.py              # todos os q_s*.json do scratchpad
  python seed_questoes.py q_s1.json   # arquivo específico (nome ou glob)
  python seed_questoes.py --dry-run   # mostra o que seria importado sem gravar

Requer: variável de ambiente AzureWebJobsStorage (connection string do Azure Storage)
        ou arquivo .env na mesma pasta com AzureWebJobsStorage=...
"""

import argparse, glob, json, os, sys, uuid
from pathlib import Path

SCRATCH = r'C:\Users\PLAURE~1.MAT\AppData\Local\Temp\claude\c--Users-p-laurenti-de-matos-Desktop-DEVP-Concursos\740a2008-d5c0-47a6-9c84-65136a545123\scratchpad'

def load_env():
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

def get_table():
    load_env()
    conn = os.environ.get('AzureWebJobsStorage', '')
    if not conn:
        print('ERRO: variável AzureWebJobsStorage não definida.')
        print('  Defina no .env ou como variável de ambiente antes de rodar.')
        sys.exit(1)
    from azure.data.tables import TableServiceClient
    svc = TableServiceClient.from_connection_string(conn)
    svc.create_table_if_not_exists('questoes')
    return svc.get_table_client('questoes')

def seed_file(path, tbl, dry_run=False):
    print(f'\n=== {Path(path).name} ===')
    with open(path, encoding='utf-8') as f:
        questions = json.load(f)
    if not isinstance(questions, list):
        print('  ERRO: arquivo não contém array')
        return 0, 0
    total = len(questions)
    print(f'  {total} questões encontradas')
    inserted = skipped = 0
    for q in questions:
        if not q.get('enunciado'):
            skipped += 1
            continue
        entity = {
            'PartitionKey': 'q',
            'RowKey': str(uuid.uuid5(uuid.NAMESPACE_DNS, q['enunciado'][:200])),
            'disciplina': q.get('disciplina', 'Específico'),
            'enunciado':  q.get('enunciado', ''),
            'a': q.get('a', ''), 'b': q.get('b', ''), 'c': q.get('c', ''),
            'd': q.get('d', ''), 'e': q.get('e', ''),
            'gabarito':   q.get('gabarito', 'a'),
            'fonte':      q.get('fonte', ''),
            'explicacao': q.get('explicacao', ''),
            'date':       q.get('date', ''),
        }
        if not dry_run:
            from azure.data.tables import UpdateMode
            tbl.upsert_entity(entity, mode=UpdateMode.REPLACE)
        inserted += 1
    print(f'  {"[DRY RUN] " if dry_run else ""}Importadas: {inserted}, puladas: {skipped}')
    return inserted, skipped

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='*', help='Arquivo(s) JSON (nome ou glob). Padrão: todos q_s*.json')
    parser.add_argument('--dry-run', action='store_true', help='Simula sem gravar')
    args = parser.parse_args()

    tbl = None if args.dry_run else get_table()

    if args.files:
        paths = []
        for pattern in args.files:
            matched = glob.glob(pattern)
            if not matched:
                matched = glob.glob(os.path.join(SCRATCH, pattern))
            paths.extend(matched)
    else:
        paths = sorted(glob.glob(os.path.join(SCRATCH, 'q_s*.json')))

    if not paths:
        print('Nenhum arquivo encontrado.'); sys.exit(1)

    total_ins = total_skip = 0
    for p in paths:
        ins, skip = seed_file(p, tbl, dry_run=args.dry_run)
        total_ins += ins
        total_skip += skip

    verb = '[DRY RUN] Seriam importadas' if args.dry_run else 'Total importado'
    print(f'\n{verb}: {total_ins} questões | puladas: {total_skip}')

if __name__ == '__main__':
    main()
