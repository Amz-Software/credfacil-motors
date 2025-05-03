from datetime import date

def calcular_data_primeira_parcela(dia_str: str) -> date:
    """
    Recebe dia_str em '1', '10' ou '20' e retorna um date
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
