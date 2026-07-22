import streamlit as st
import datetime
import requests
import pandas as pd
import re
try:
    import gspread
except ImportError:
    gspread = None
try:
    from geopy.geocoders import ArcGIS
except ImportError:
    ArcGIS = None
try:
    from streamlit_option_menu import option_menu
except ImportError:
    option_menu = None

# --- CONEXÃO COM O GOOGLE SHEETS ---
gc = None
planilha = None
if gspread is not None:
    try:
        gc = gspread.service_account(filename='credenciais.json')
        planilha = gc.open('App Pytohn').sheet1
    except Exception as e:
        planilha = None
        st.error(f"Erro de conexão com o Google Sheets: {e}")
else:
    st.error("Módulo gspread não encontrado. Instale gspread para usar Google Sheets.")

def carregar_dados():
    if planilha is None:
        return pd.DataFrame(columns=["Data_Pedido", "Ação", "Cliente", "Endereço", "Cidade", "Prazo", "Valor", "Status", "Data_Entrega", "Motorista"])
    try:
        dados = planilha.get_all_records()
        if not dados:
            return pd.DataFrame(columns=["Data_Pedido", "Ação", "Cliente", "Endereço", "Cidade", "Prazo", "Valor", "Status", "Data_Entrega", "Motorista"])
        return pd.DataFrame(dados)
    except Exception:
        return pd.DataFrame()

def salvar_pedido(data, acao, cliente, endereco, cidade, prazo, valor, status):
    if planilha is None:
        raise RuntimeError("Google Sheets não está disponível. Verifique as credenciais e dependências.")
    nova_linha = [data, acao, cliente, endereco, cidade, prazo, valor, status, "", ""]
    planilha.append_row(nova_linha)

# --- GPS: BUSCADOR INTELIGENTE DE COORDENADAS (NOVO MOTOR ARCGIS) ---
if hasattr(st, "cache_data"):
    @st.cache_data
    def pegar_coordenadas(endereco, cidade):
        if ArcGIS is None:
            return None, None
        geolocator = ArcGIS()
        end_str = str(endereco).strip()
        
        if "http" in end_str and len(end_str.split()) == 1:
            return None, None
            
        try:
            busca_exata = f"{end_str}, {cidade}, SP, Brasil"
            location = geolocator.geocode(busca_exata, timeout=5)
            if location:
                return location.latitude, location.longitude
                
            endereco_limpo = re.sub(r'(?i)\b(quadra|qd|lote|lt|casa)\s*[a-z0-9-]+\b\s*,?\s*', '', end_str).strip()
            endereco_limpo = re.sub(r'http\S+', '', endereco_limpo).strip() 
            
            if endereco_limpo:
                busca_condominio = f"{endereco_limpo}, {cidade}, SP, Brasil"
                location = geolocator.geocode(busca_condominio, timeout=5)
                if location:
                    return location.latitude, location.longitude
                    
            return None, None
        except:
            return None, None
else:
    def pegar_coordenadas(endereco, cidade):
        return None, None

# --- MOTOR DE VENCIMENTOS AUTOMÁTICO ---
def verificar_e_calcular_vencimentos(df):
    if df.empty or 'Data_Entrega' not in df.columns:
        return df
        
    hoje = datetime.datetime.now().date()
    df['Vencimento_Calculado'] = "-"
    df['Dias_na_Rua'] = "-"

    for index, row in df.iterrows():
        if pd.notna(row.get('Data_Entrega')) and str(row.get('Data_Entrega')).strip() != "":
            try:
                data_entrega = datetime.datetime.strptime(str(row['Data_Entrega']), "%d/%m/%Y").date()
                
                prazo_str = str(row['Prazo']).lower()
                if "mensal" in prazo_str:
                    dias_prazo = 30
                else:
                    numeros = re.findall(r'\d+', prazo_str)
                    dias_prazo = int(numeros[0]) if numeros else 0
                    
                data_vencimento = data_entrega + datetime.timedelta(days=dias_prazo)
                df.at[index, 'Vencimento_Calculado'] = data_vencimento.strftime("%d/%m/%Y")
                
                dias_passados = (hoje - data_entrega).days
                df.at[index, 'Dias_na_Rua'] = f"{dias_passados} dias"
                
                if hoje > data_vencimento and row['Status'] == '🟢 No Prazo':
                    linha_real = index + 2
                    planilha.update_cell(linha_real, 8, '🔴 Vencida')
                    df.at[index, 'Status'] = '🔴 Vencida' 
            except Exception as e:
                continue
    return df

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gallo - Logística", page_icon="🚛", layout="wide")

# ==========================================
# INJEÇÃO DO NOVO DESIGN (IDENTIDADE VISUAL)
# ==========================================
estilo_customizado = """
<style>
    /* 1. FUNDO DA TELA PRINCIPAL (Azul bem mais escuro) */
    .stApp {
        background-color: rgb(0, 10, 40) !important; 
    }
    
    /* Remove a faixa cinza do topo para integrar 100% com o fundo */
    [data-testid="stHeader"] {
        background-color: transparent !important;
    }

    /* 2. BARRA LATERAL (Azul Principal) */
    [data-testid="stSidebar"] {
        background-color: rgb(1, 27, 101) !important;
    }
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    
    /* Ajuste do tamanho da fonte do Menu */
    [data-testid="stSidebar"] .stRadio p {
        font-size: 22px !important;
        font-weight: 600 !important;
        margin: 0 !important; 
    }

    /* 3. MENU LATERAL: Efeito de Botão com Borda e Zoom (Estilo do Vídeo) */
    [data-testid="stSidebar"] label[data-baseweb="radio"] {
        padding: 12px 15px !important; 
        border-radius: 25px !important; 
        border: 2px solid transparent !important; /* Borda invisível para não pular a tela */
        transition: all 0.3s ease-in-out !important; /* Animação suave igual ao vídeo */
        margin-bottom: 8px !important; 
        cursor: pointer !important;
    }
    
    /* Quando passar o mouse: Azul escuro, borda branca e aumenta de tamanho */
    [data-testid="stSidebar"] label[data-baseweb="radio"]:hover {
        background-color: rgb(0, 10, 40) !important; /* Azul mais escuro que você pediu */
        transform: scale(1.02) !important; /* Dá aquele zoomzinho para frente */
        border: 2px solid white !important; /* Borda branca acesa */
    }

    /* 4. BOTÕES DE AÇÃO PRINCIPAIS (Vermelho) */
    .stButton > button {
        background-color: rgb(254, 0, 0) !important;
        color: white !important;
        font-size: 20px !important;
        font-weight: bold !important;
        height: 60px !important;
        border-radius: 10px !important;
        border: none !important;
        box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.4) !important;
        transition: all 0.3s ease-in-out !important;
    }
    
    .stButton > button:hover {
        background-color: rgb(1, 27, 101) !important;
        color: white !important;
        transform: scale(1.02) !important;
        border: 2px solid white !important;
    }
    
    /* Ajustando a cor do texto geral */
    p, h1, h2, h3, h4, h5, h6, label {
        color: #f0f2f6 !important;
    }
</style>
"""
st.markdown(estilo_customizado, unsafe_allow_html=True)
# ==========================================

# --- MENU LATERAL ---
with st.sidebar:
    st.image("logo.png", use_container_width=True)
    st.markdown("---")
    
    menu = option_menu(
        menu_title=None, 
        options=[
            "🏠 Visão Geral", 
            "🗺️ Mapa de Logística",
            "➕ Novo Pedido", 
            "🔄 Solicitar Serviço", 
            "📅 Agendamentos", 
            "📋 Gestão de Pátio", 
            "🕰️ Histórico", 
            "✏️ Gerenciar Pedidos"
        ],
        icons=["", "", "", "", "", "", "", ""], 
        default_index=0,
        styles={
            "container": {
                "padding": "0!important", 
                "background-color": "rgb(1, 27, 101)", # Fundo exato da barra lateral
                "border": "none"
            },
            "icon": {
                "display": "none" 
            },
            "nav-link": {
                "font-size": "20px", 
                "text-align": "left", 
                "margin": "8px 0px", 
                "color": "white",
                "background-color": "transparent", 
                "border-radius": "12px",
                "border": "2px solid transparent", 
                "transition": "all 0.3s ease-in-out" 
            },
            "nav-link:hover": {
                "background-color": "rgb(30, 90, 200)", # Azul mais claro ao passar o mouse
                "border": "2px solid white",          
                "transform": "scale(1.05)"            
            },
            "nav-link-selected": {
                "background-color": "rgb(0, 10, 40)", # Vermelho Gallo na aba ativa
                "font-weight": "bold",
                "color": "white",
                "border": "2px solid transparent"
            }
        }
    )

# --- TELA: VISÃO GERAL ---
if menu == "🏠 Visão Geral":
    st.header("🏠 Visão Geral do Pátio")
    st.markdown("O sistema verifica os prazos automaticamente baseado na data em que a equipe entregou a caçamba.")

    df_bruto = carregar_dados()
    df = verificar_e_calcular_vencimentos(df_bruto)

    if not df.empty:
        para_entregar = len(df[df['Status'] == '🔵 Para Entregar'])
        no_prazo = len(df[df['Status'] == '🟢 No Prazo'])
        vencidas = len(df[df['Status'] == '🔴 Vencida'])
        agendados = len(df[df['Status'] == '📅 Agendado'])
    else:
        para_entregar = no_prazo = vencidas = agendados = 0

    col1, col2, col3, col4 = st.columns(4)
    col1.info(f"🔵 P/ Entregar: {para_entregar}")
    col2.success(f"🟢 No Prazo: {no_prazo}")
    col3.error(f"🔴 Vencidas: {vencidas}")
    col4.warning(f"📅 Agendados: {agendados}")

    st.markdown("---")
    st.subheader("Caçambas Ativas na Rua")
    if not df.empty:
        df_ativas = df[df['Status'].isin(['🟢 No Prazo', '🔴 Vencida', '🟣 Na Diária'])]
        st.dataframe(df_ativas, use_container_width=True)

# --- TELA: MAPA DE LOGÍSTICA ---
elif menu == "🗺️ Mapa de Logística":
    st.header("🗺️ Mapa Regional de Caçambas")
    st.markdown("Veja a localização exata das caçambas ativas para planejar as rotas da equipe.")
    
    df_bruto = carregar_dados()
    df = verificar_e_calcular_vencimentos(df_bruto)
    
    if not df.empty:
        df_ativas = df[df['Status'].isin(['🔵 Para Entregar', '🟢 No Prazo', '🔴 Vencida', '🟣 Na Diária'])]
        
        if df_ativas.empty:
            st.info("Nenhuma caçamba ativa ou pendente para mostrar no mapa.")
        else:
            with st.spinner("Buscando sinal de GPS dos endereços... (Isso é feito apenas uma vez por endereço)"):
                lats = []
                lons = []
                
                for index, row in df_ativas.iterrows():
                    lat, lon = pegar_coordenadas(str(row['Endereço']), str(row['Cidade']))
                    lats.append(lat)
                    lons.append(lon)

                df_ativas = df_ativas.copy() 
                df_ativas['LAT'] = lats
                df_ativas['LON'] = lons
                
                df_mapa = df_ativas.dropna(subset=['LAT', 'LON'])

            if not df_mapa.empty:
                st.map(df_mapa, size=20, color="#FF0000")
                st.success(f"{len(df_mapa)} caçambas localizadas e plotadas no mapa com sucesso!")
                
                if len(df_mapa) < len(df_ativas):
                    st.warning(f"{len(df_ativas) - len(df_mapa)} endereço(s) continham apenas links do Google ou nomes muito curtos e foram ignorados no mapa para evitar falhas.")
            else:
                st.warning("O sistema não conseguiu localizar as coordenadas exatas no GPS mundial.")
                
# --- TELA: NOVO PEDIDO ---
elif menu == "➕ Novo Pedido":
    st.header("➕ Lançar Novo Pedido")
    
    with st.form("form_novo_pedido"):
        acao = st.radio("Ação", ["ENTREGAR", "RETIRAR", "TROCAR"], horizontal=True)
        cliente = st.text_input("Nome do Cliente (ex: Gilberto)")
        
        col_end, col_cid = st.columns([3, 1])
        endereco = col_end.text_input("Endereço (Rua, Número, Bairro ou Nome do Condomínio)")
        cidade = col_cid.selectbox("Cidade", ["Sumaré", "Americana", "Nova Odessa", "Santa Bárbara d'Oeste"])
        
        col_prazo, col_valor, col_data = st.columns(3)
        prazo = col_prazo.selectbox("Prazo Contratado", ["3 dias", "7 dias", "10 dias", "15 dias", "Mensal"])
        valor = col_valor.number_input("Valor (R$)", min_value=0.0, format="%.2f")
        data_agendada = col_data.date_input("Agendar Entrega para:", datetime.date.today())

        submit_button = st.form_submit_button("🚀 Registrar Pedido")

        if submit_button:
            data_atual = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            data_formatada = data_agendada.strftime("%d/%m/%Y")
            
            if data_agendada > datetime.date.today():
                status_inicial = "📅 Agendado"
            else:
                status_inicial = "🔵 Para Entregar"

            salvar_pedido(data_atual, acao, cliente, endereco, cidade, prazo, valor, status_inicial)
            total_linhas = len(planilha.get_all_values())
            
            if status_inicial == "🔵 Para Entregar":
                mensagem_discord = f"""ID: {total_linhas}
{acao.upper()}
{cliente}
{endereco} ({cidade.upper()})
{prazo} R${valor:.2f}
."""
                webhook_url = "https://discord.com/api/webhooks/1529205321556299858/dTi8SSdSRcHj_tyEpWHpUxfZyaSOh1o8b0ip0vSpPhB0JgG0l5itCZk9FfqLP_HRJhRm"
                try:
                    requests.post(webhook_url, json={"content": mensagem_discord})
                    st.success(f"Pedido de {cliente} salvo e enviado para o Discord!")
                except Exception as e:
                    st.error(f"Erro de conexão com o Discord: {e}")
            else:
                st.success(f"Pedido de {cliente} salvo nos Agendamentos para o dia {data_formatada}!")

# --- TELA: SOLICITAR SERVIÇO (TROCA/RETIRADA) ---
elif menu == "🔄 Solicitar Serviço":
    st.header("🔄 Solicitar Troca ou Retirada")
    st.markdown("Selecione um cliente que já está com a caçamba para solicitar um novo serviço.")

    df = carregar_dados()
    if not df.empty:
        df['Linha_Planilha'] = df.index + 2
        df_ativas = df[df['Status'].isin(['🟢 No Prazo', '🔴 Vencida', '🟣 Na Diária'])]
        
        if df_ativas.empty:
            st.info("Nenhuma caçamba ativa na rua no momento para trocar ou retirar.")
        else:
            opcoes = df_ativas['Linha_Planilha'].astype(str) + " - " + df_ativas['Cliente'] + " (" + df_ativas['Endereço'] + ")"
            pedido_selecionado = st.selectbox("Selecione a Caçamba:", opcoes)

            linha_real = int(pedido_selecionado.split(" - ")[0])
            dados_atuais = df[df['Linha_Planilha'] == linha_real].iloc[0]

            nova_acao = st.radio("O que a equipe deve fazer?", ["TROCAR", "RETIRAR"], horizontal=True)

            if nova_acao == "TROCAR":
                col_prazo, col_valor = st.columns(2)
                lista_prazos = ["3 dias", "7 dias", "10 dias", "15 dias", "Mensal"]
                prazo_atual = dados_atuais['Prazo'] if dados_atuais['Prazo'] in lista_prazos else "3 dias"
                
                novo_prazo = col_prazo.selectbox("Novo Prazo Contratado", lista_prazos, index=lista_prazos.index(prazo_atual))
                
                valor_atual = float(str(dados_atuais['Valor']).replace(',', '.')) if str(dados_atuais['Valor']).replace('.', '', 1).replace(',', '', 1).isdigit() else 0.0
                novo_valor = col_valor.number_input("Valor da Nova Caçamba (R$)", min_value=0.0, value=valor_atual, format="%.2f")
            
            else: 
                forma_pagamento = st.radio("Forma de Pagamento na Retirada:", ["Pix", "Dinheiro"], horizontal=True)
                if forma_pagamento == "Dinheiro":
                    novo_valor = st.number_input("Valor a Receber na Obra (R$)", min_value=0.0, format="%.2f")
                else:
                    novo_valor = 0.0

            if st.button("🚀 Enviar Ordem para o Discord"):
                data_atual = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                
                status_antigo = "⚫ Finalizada" 
                planilha.update_cell(linha_real, 8, status_antigo)

                if nova_acao == "TROCAR":
                    salvar_pedido(data_atual, nova_acao, dados_atuais['Cliente'], dados_atuais['Endereço'], dados_atuais['Cidade'], novo_prazo, novo_valor, "🔵 Para Entregar")
                else:
                    salvar_pedido(data_atual, nova_acao, dados_atuais['Cliente'], dados_atuais['Endereço'], dados_atuais['Cidade'], "-", novo_valor, "🔵 Para Entregar")
                
                novo_id = len(planilha.get_all_values())

                if nova_acao == "TROCAR":
                    mensagem_discord = f"""ID: {novo_id}
{nova_acao}
{dados_atuais['Cliente']}
{dados_atuais['Endereço']} ({dados_atuais['Cidade'].upper()})
{novo_prazo} R${novo_valor:.2f}
."""
                else: 
                    if forma_pagamento == "Pix":
                        mensagem_discord = f"""ID: {novo_id}
{nova_acao} (PIX)
{dados_atuais['Cliente']}
{dados_atuais['Endereço']} ({dados_atuais['Cidade'].upper()})
."""
                    else: 
                        mensagem_discord = f"""ID: {novo_id}
{nova_acao} (DINHEIRO)
{dados_atuais['Cliente']}
{dados_atuais['Endereço']} ({dados_atuais['Cidade'].upper()})
R${novo_valor:.2f}
."""

                webhook_url = "https://discord.com/api/webhooks/1529205321556299858/dTi8SSdSRcHj_tyEpWHpUxfZyaSOh1o8b0ip0vSpPhB0JgG0l5itCZk9FfqLP_HRJhRm"
                try:
                    requests.post(webhook_url, json={"content": mensagem_discord})
                    st.success(f"Nova linha criada na planilha! Ordem de {nova_acao} enviada para a equipe com sucesso.")
                except Exception as e:
                    st.error(f"Erro de conexão: {e}")

# --- TELA: AGENDAMENTOS ---
elif menu == "📅 Agendamentos":
    st.header("📅 Pedidos Agendados")
    st.write("Caçambas programadas para datas futuras. Libere o pedido quando chegar o dia.")
    
    df = carregar_dados()
    if not df.empty:
        df['Linha_Planilha'] = df.index + 2
        df_agendados = df[df['Status'] == '📅 Agendado']
        
        if df_agendados.empty:
            st.info("Nenhum pedido agendado no momento.")
        else:
            st.dataframe(df_agendados, use_container_width=True)
            
            st.markdown("---")
            st.subheader("Liberar Agendamento para Hoje")
            opcoes_agendados = df_agendados['Linha_Planilha'].astype(str) + " - " + df_agendados['Cliente'] + " (" + df_agendados['Endereço'] + ")"
            agendamento_selecionado = st.selectbox("Selecione o pedido para liberar:", opcoes_agendados)

            if st.button("🚀 Enviar para o Discord (Liberar Hoje)"):
                linha_real = int(agendamento_selecionado.split(" - ")[0])
                dados_atuais = df[df['Linha_Planilha'] == linha_real].iloc[0]

                planilha.update_cell(linha_real, 8, "🔵 Para Entregar")

                mensagem_discord = f"""ID: {linha_real}
{dados_atuais['Ação'].upper()}
{dados_atuais['Cliente']}
{dados_atuais['Endereço']} ({dados_atuais['Cidade'].upper()})
{dados_atuais['Prazo']} R${dados_atuais['Valor']}
."""
                webhook_url = "https://discord.com/api/webhooks/1529205321556299858/dTi8SSdSRcHj_tyEpWHpUxfZyaSOh1o8b0ip0vSpPhB0JgG0l5itCZk9FfqLP_HRJhRm"
                try:
                    requests.post(webhook_url, json={"content": mensagem_discord})
                    st.success(f"Agendamento liberado e enviado para o Discord com sucesso!")
                except Exception as e:
                    st.error(f"Erro: {e}")

# --- TELA: GESTÃO DE PÁTIO ---
elif menu == "📋 Gestão de Pátio":
    st.header("📋 Controle de Pátio e Retiradas")
    st.write("Visão detalhada de todas as caçambas na rua e ordens de retirada.")
    
    df_bruto = carregar_dados()
    df = verificar_e_calcular_vencimentos(df_bruto)
    
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        
# --- TELA: HISTÓRICO ---
elif menu == "🕰️ Histórico":
    st.header("🕰️ Histórico Completo de Locações (Ano 2026)")
    st.write("Acompanhe tudo o que já foi finalizado e faturado.")
    df_bruto = carregar_dados()
    df = verificar_e_calcular_vencimentos(df_bruto)
    st.dataframe(df, use_container_width=True)

# --- TELA: GERENCIAR PEDIDOS ---
elif menu == "✏️ Gerenciar Pedidos":
    st.header("✏️ Editar ou Excluir Pedidos")
    df = carregar_dados()
    
    if df.empty:
        st.warning("Nenhum pedido encontrado na planilha.")
    else:
        df['Linha_Planilha'] = df.index + 2
        opcoes = df['Linha_Planilha'].astype(str) + " - " + df['Cliente'] + " (" + df['Prazo'] + ")"
        pedido_selecionado = st.selectbox("Selecione o pedido:", opcoes)
        
        if pedido_selecionado:
            linha_real = int(pedido_selecionado.split(" - ")[0])
            dados_atuais = df[df['Linha_Planilha'] == linha_real].iloc[0]
            
            with st.form("form_editar"):
                st.write(f"**Cliente:** {dados_atuais['Cliente']} | **Endereço:** {dados_atuais['Endereço']}")
                
                lista_prazos = ["3 dias", "7 dias", "10 dias", "15 dias", "Mensal"]
                novo_prazo = st.selectbox("Atualizar Prazo:", lista_prazos, index=lista_prazos.index(dados_atuais['Prazo']) if dados_atuais['Prazo'] in lista_prazos else 0)
                
                lista_status = ["🔵 Para Entregar", "🟢 No Prazo", "🔴 Vencida", "🟣 Na Diária", "⚫ Finalizada", "📅 Agendado"]
                index_status = lista_status.index(dados_atuais['Status']) if dados_atuais['Status'] in lista_status else 0
                novo_status = st.selectbox("Atualizar Status:", lista_status, index=index_status)
                
                col_salvar, col_excluir = st.columns(2)
                btn_salvar = col_salvar.form_submit_button("💾 Salvar Alterações")
                btn_excluir = col_excluir.form_submit_button("🗑️ Excluir Pedido")
                
                if btn_salvar:
                    planilha.update_cell(linha_real, 6, novo_prazo)
                    planilha.update_cell(linha_real, 8, novo_status)
                    st.success("✅ Pedido atualizado com sucesso! (Recarregue a página na barra lateral)")
                
                if btn_excluir:
                    planilha.delete_rows(linha_real)
                    st.success("🗑️ Pedido excluído com sucesso! (Recarregue a página na barra lateral)")