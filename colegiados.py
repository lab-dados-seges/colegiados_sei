import streamlit as st
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
import pandas as pd
import os
from io import BytesIO
from selenium.common.exceptions import NoSuchElementException
import pyshorteners

# Função para realizar login
def realizar_login(url, login1, password1, orgao1):
    try:
        driver = webdriver.Chrome()
        driver.implicitly_wait(0.5)
        driver.get(url)

        login = driver.find_element(By.XPATH, '//*[@id="txtUsuario"]')
        password = driver.find_element(By.XPATH, '//*[@id="pwdSenha"]')
        orgao = driver.find_element(By.XPATH, '//*[@id="selOrgao"]')
        submit_button = driver.find_element(By.XPATH, '//*[@id="Acessar"]')

        login.send_keys(login1)
        password.send_keys(password1)
        orgao.send_keys(orgao1)
        submit_button.click()
        time.sleep(3)

        print("Login realizado com sucesso!")
        
        time.sleep(1)
        searching = driver.find_element(By.XPATH, '//*[@id="infraMenu"]/li[14]/a/span')
        searching.click()
        time.sleep(1)
        
        docum_pesq = driver.find_element(By.XPATH, '//*[@id="divOptDocumentos"]/div')
        docum_pesq.click()
        time.sleep(0.3)
        
        chktram = driver.find_element(By.XPATH, '//*[id="chkSinTramitacao"]/div')
        chktram.click()
        time.sleep(0.2)

        sel_orgao = driver.find_element(By.XPATH, '//*[@id="divSinRestringirOrgao"]/div')
        sel_orgao.click()
        time.sleep(0.5)

        espec_pesq = driver.find_element(By.XPATH, '//*[@id="q"]')
        espec_pesq.send_keys('indicação ou retificação ou nomear ou nomeação ou ratificar ou retificar ou representante ou exoneração')
        
        tipo_process = driver.find_element(By.XPATH, '//*[@id="selTipoProcedimentoPesquisa"]')
        tipo_process.send_keys("Gestão Administrativa: Conselhos, Comissões, Comitês, Grupos de Trabalho e Juntas")
        time.sleep(0.5)

        b_pesq = driver.find_element(By.XPATH, '//*[@id="sbmPesquisar"]')
        b_pesq.click()
        time.sleep(3)

        print("Busca realizada com sucesso.\nRestringindo em Colegiados e dentro do MGI.\n\nOs Externo entram como MGI.")
        return driver
    except Exception as e:
        print(f"Erro durante a busca: {e}")
        return None

def extrair_dados(driver):     
    def remove_items(lista, item): 
        return [i for i in lista if i != item]
   
    tree_elements = driver.find_elements(By.XPATH, '//*[@class="pesquisaTituloEsquerda"]/a')
    list_tree = [element.text for element in tree_elements]
    trees = remove_items(list_tree, '')

    abts = driver.find_elements(By.XPATH, '//*[@class="pesquisaSnippet"]')
    list_abts = [element.text for element in abts]
    
    max_length = 500
    list_abts = [abt for abt in list_abts if len(abt) <= max_length]

    unidades = driver.find_elements(By.XPATH, '//*[@class="pesquisaMetatag"]')
    list_uni = [element.text.split(':') for element in unidades]
    info = [sublist_uni[1] for sublist_uni in list_uni if len(sublist_uni) > 1]

    rows = driver.find_elements(By.XPATH, '//*[@id="conteudo"]/table/tbody/tr')
    links = []
    files_name = []
    for i in range(1, len(rows)+1, 3):
        try:
            a = driver.find_element(By.XPATH, f'//*[@id="conteudo"]/table/tbody/tr[{i}]/td[2]/a')
            time.sleep(0.5)
            link = a.get_attribute('href')
            file_name = a.text
            links.append(link)
            files_name.append(file_name)
        except Exception as e:
            print(f"Erro ao processar a linha {i}: {e}")

    shortener = pyshorteners.Shortener(api_key='your_api_key', provider='isgd')
    links_curtos = []
    erros = []
    
    for link in links:
        try:
            base_url, hash_value = link.split('infra_hash=')
            if len(base_url) > 1000:
                raise ValueError(f"Link base muito longo: {base_url}")
            link_curto = shortener.tinyurl.short(base_url)
            time.sleep(0.5)
            link_com_hash = link_curto + 'infra_hash=' + hash_value
            links_curtos.append(link_com_hash)
            time.sleep(0.5)
        except Exception as e:
            erros.append((link, str(e)))
            links_curtos.append(None)
            
    dados = {
        "Número do Processo": trees[::2],
        "Documento": trees[1::2],
        "Resumo": list_abts,
        "Unidade": info[::3],
        "Usuário": info[1::3],
        "Data de Inclusão": info[2::3],
        "Links": links_curtos
    }
        
    df = pd.DataFrame(dados)
    
    return df, links, files_name

def navegar_paginas(driver):
    dados_consolidados = pd.DataFrame()
    links_consolidados = []
    files_name_consolidados = []

    while True:
        try:
            df_pagina, links, files_name = extrair_dados(driver)
            dados_consolidados = pd.concat([dados_consolidados, df_pagina], ignore_index=True)
            links_consolidados.extend(links)
            files_name_consolidados.extend(files_name)

            next_page = driver.find_element("xpath", '//*[@id="conteudo"]/div[2]/div[3]/a')
            proxima_href = next_page.get_attribute('href')
            time.sleep(3)
            if not proxima_href:
                print("Não há mais páginas. Encerrando navegação.")
                break

            next_page.click()
            time.sleep(10)

        except NoSuchElementException:
            print("Botão 'Próxima' não encontrado. Encerrando navegação.")
            break

        except Exception as e:
            print(f"Erro inesperado: {e}")
            break

    return dados_consolidados, links_consolidados, files_name_consolidados

def gerar_excel(dados_consolidados):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        dados_consolidados.to_excel(writer, index=False, sheet_name="Dados")
    processed_data = output.getvalue()
    return processed_data

def baixar_documentos(driver, links, files_name):
    original_window = driver.current_window_handle 
    for index, (link, name) in enumerate(zip(links, files_name)):
        driver.switch_to.new_window('tab')
        driver.get(link)
        with open(f'./colegiados_{name}.html', 'w', encoding='utf-8', errors='ignore') as file:
            file.write(driver.page_source)        
        driver.close()
        driver.switch_to.window(original_window)

# Interface Streamlit
st.title("Colegiados no SEI")

st.header("Configurações de Login")
url = st.text_input("URL do SEI", value="https://sei.economia.gov.br/")
login1 = st.text_input("Login")
password1 = st.text_input("Senha", type="password")
orgao1 = st.text_input("Órgão")

if st.button("Executar Busca"):
    with st.spinner("Realizando login e extração..."):
        driver = realizar_login(url, login1, password1, orgao1)
        if driver:
            df, links, files_name = navegar_paginas(driver)
            st.dataframe(df)
            
            excel_data = gerar_excel(df)
            st.download_button(
                label="Baixar dados em Excel",
                data=excel_data,
                file_name="dados_sei.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            
            if st.button("Baixar documentos em HTML"):
                with st.spinner("Baixando documentos..."):
                    baixar_documentos(driver, links, files_name)
                st.success("Documentos baixados com sucesso!")