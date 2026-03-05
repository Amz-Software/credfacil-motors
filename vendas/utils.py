import os
import uuid
from datetime import date

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile


TEMP_UPLOAD_DIR = os.path.join(settings.MEDIA_ROOT, 'temp_uploads')

# Campos de arquivo do ComprovantesCliente
COMPROVANTES_FILE_FIELDS = [
    'documento_identificacao_frente',
    'documento_identificacao_verso',
    'comprovante_residencia',
    'consulta_serasa',
    'foto_cliente',
    'foto_cnh',
]


def save_temp_files(session, files):
    """
    Salva arquivos do request.FILES em um diretório temporário e
    armazena os caminhos na sessão para recuperar após erros de validação.
    """
    os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

    temp_files = session.get('temp_comprovantes', {})

    for field_name in COMPROVANTES_FILE_FIELDS:
        if field_name in files:
            uploaded = files[field_name]
            # Lê o conteúdo do arquivo (seek(0) para garantir leitura do início)
            if hasattr(uploaded, 'seek'):
                uploaded.seek(0)
            content = uploaded.read()
            if not content:
                continue

            ext = os.path.splitext(uploaded.name)[1]
            temp_name = f"{uuid.uuid4().hex}{ext}"
            temp_path = os.path.join(TEMP_UPLOAD_DIR, temp_name)

            with open(temp_path, 'wb') as f:
                f.write(content)

            # Remove arquivo temporário anterior se existir
            old = temp_files.get(field_name)
            if old and os.path.exists(old['path']):
                os.remove(old['path'])

            temp_files[field_name] = {
                'path': temp_path,
                'name': uploaded.name,
                'content_type': getattr(uploaded, 'content_type', 'application/octet-stream'),
            }

    session['temp_comprovantes'] = temp_files
    session.modified = True


def restore_temp_files(session, request_files):
    """
    Constrói um dicionário simples com todos os arquivos:
    - Arquivos novos do request.FILES
    - Arquivos temporários da sessão para campos que não foram re-enviados
    Retorna um dict simples compatível com o parâmetro `files` do Django Form.
    """
    temp_files = session.get('temp_comprovantes', {})

    # Começa com um dict simples contendo os arquivos do request
    result = {}
    for key in request_files:
        result[key] = request_files[key]

    if not temp_files:
        return result

    # Adiciona temp files para campos ausentes
    for field_name in COMPROVANTES_FILE_FIELDS:
        if field_name not in result and field_name in temp_files:
            info = temp_files[field_name]
            if os.path.exists(info['path']):
                with open(info['path'], 'rb') as f:
                    content = f.read()
                if content:
                    result[field_name] = SimpleUploadedFile(
                        name=info['name'],
                        content=content,
                        content_type=info['content_type'],
                    )

    return result


def get_temp_field_names(session):
    """
    Retorna a lista de nomes de campos que têm arquivos temporários salvos.
    """
    temp_files = session.get('temp_comprovantes', {})
    return [
        field_name for field_name, info in temp_files.items()
        if os.path.exists(info['path'])
    ]


def get_temp_file_urls(session):
    """
    Retorna um dicionário {field_name: url} para previews de arquivos
    temporários no template.
    """
    temp_files = session.get('temp_comprovantes', {})
    urls = {}
    for field_name, info in temp_files.items():
        if os.path.exists(info['path']):
            # URL relativa ao MEDIA_URL
            rel_path = os.path.relpath(info['path'], settings.MEDIA_ROOT)
            urls[field_name] = settings.MEDIA_URL + rel_path.replace(os.sep, '/')
    return urls


def clean_temp_files(session):
    """
    Remove todos os arquivos temporários da sessão após salvar com sucesso.
    """
    temp_files = session.pop('temp_comprovantes', {})
    for field_name, info in temp_files.items():
        if os.path.exists(info['path']):
            os.remove(info['path'])
    session.modified = True

def calcular_data_primeira_parcela(dia_str: str) -> date:
    """
    Recebe dia_str em '1' ou '16' e retorna um date
    correspondente ao próximo dia de pagamento.
    
    - Se hoje for <= dia, retorna esse mês no dia indicado.
    - Se hoje for > dia, retorna o dia indicado do próximo mês.
    """
    dia = int(dia_str)
    hoje = date.today()
    ano = hoje.year
    mes = hoje.month

    # Se ainda não chegamos ao dia no mês atual, usamos este mês
    if hoje.day <= dia:
        return date(ano, mes, dia)
    
    # Caso contrário, avançamos para o próximo mês
    if mes == 12:
        ano += 1
        mes = 1
    else:
        mes += 1

    return date(ano, mes, dia)
