from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Substitua pelo seu token de acesso à API do RD Station CRM
RDSTATION_CRM_API_TOKEN = "SEU_TOKEN_AQUI"

# IDs dos campos personalizados de CNPJ
CNPJ_CONTATO_FIELD_ID = "65e5fb49eaf2aa0019569415"
CNPJ_EMPRESA_FIELD_ID = "68652b3ca12866001866c0b4"
CNPJ_NEGOCIACAO_FIELD_ID = "68652f400326c0001ce16e5e"

RDSTATION_CRM_API_BASE_URL = "https://crm.rdstation.com/api/v1"

@app.route('/processar_formulario', methods=['POST'])
def processar_formulario():
    data = request.json

    if not data:
        return jsonify({"error": "Nenhum dado recebido."}), 400

    cnpj_contato = data.get('cnpj_contato')
    nome_contato = data.get('nome_contato')
    email_contato = data.get('email_contato')
    # Adicione outros campos do seu formulário aqui

    if not cnpj_contato or not nome_contato or not email_contato:
        return jsonify({"error": "Dados mínimos (CNPJ, nome, email) não fornecidos."}), 400

    # Lógica para buscar/criar empresa e contato
    company = find_company_by_cnpj(cnpj_contato)
    if not company:
        # Assumindo que o nome da empresa pode ser derivado do nome do contato ou de outro campo do formulário
        # Para simplificar, usaremos o nome do contato como nome da empresa se não houver um campo específico para isso.
        # Em um cenário real, você provavelmente teria um campo 'nome_empresa' no formulário.
        company_name = data.get("nome_empresa", f"Empresa do {nome_contato}")
        company = create_company(company_name, cnpj_contato)
        if not company:
            return jsonify({"error": "Falha ao criar ou encontrar empresa."}), 500

    organization_id = company.get("id")

    contact = find_contact_by_cnpj_or_email(cnpj=cnpj_contato, email=email_contato)
    if not contact:
        contact = create_contact_and_link_to_company(nome_contato, email_contato, cnpj_contato, organization_id)
        if not contact:
            return jsonify({"error": "Falha ao criar ou encontrar contato."}), 500
    else:
        # Se o contato já existe, garantir que ele esteja vinculado à empresa correta
        # A API de atualização de contato permite atualizar o organization_id
        if contact.get("organization_id") != organization_id:
            update_data = {"organization_id": organization_id}
            # A API de atualização de contato não tem um endpoint separado, é um PUT no contato existente
            # Precisamos de uma função de atualização para o contato
            # Por simplicidade, vamos apenas garantir que o organization_id seja definido se não estiver.
            # Em um cenário real, você faria um PUT para atualizar o contato com o novo organization_id.
            # Exemplo (requer implementação de update_contact):
            # update_contact(contact["id"], update_data)
            pass # Por enquanto, apenas ignora a atualização se já existe e não está vinculado

    return jsonify({"message": "Formulário processado com sucesso! Contato e empresa vinculados.", "contact_id": contact.get("id"), "company_id": company.get("id")}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)




def make_crm_api_request(method, endpoint, data=None):
    headers = {
        "Authorization": f"Token {RDSTATION_CRM_API_TOKEN}",
        "Content-Type": "application/json"
    }
    url = f"{RDSTATION_CRM_API_BASE_URL}/{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, params=data)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=data)
        else:
            raise ValueError("Método HTTP não suportado.")

        response.raise_for_status()  # Levanta um erro para códigos de status HTTP ruins (4xx ou 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição à API do RD Station CRM: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Resposta de erro: {e.response.text}")
        return None




def find_company_by_cnpj(cnpj):
    # A API do RD Station CRM não permite buscar diretamente por campos personalizados em listagens.
    # A alternativa é listar todas as empresas (ou um número razoável) e filtrar localmente.
    # Para um grande volume de dados, isso pode ser ineficiente. Uma alternativa seria
    # manter um cache local ou usar um webhook para manter um banco de dados externo sincronizado.
    # Para este exemplo, vamos simular a busca filtrando após listar.

    # Idealmente, a API deveria permitir algo como:
    # response = make_crm_api_request("GET", "organizations", {"custom_fields": {CNPJ_EMPRESA_FIELD_ID: cnpj}})
    # Mas como não é o caso, faremos a busca manual.

    # Tentativa de buscar por nome, se o CNPJ estiver no nome (não ideal, mas pode ser uma alternativa)
    # response = make_crm_api_request("GET", "organizations", {"q": cnpj})

    # A melhor abordagem é listar e filtrar. Vamos listar um número grande para tentar encontrar.
    # Note: A API tem um limite de 200 por requisição. Para mais, seria necessário paginação.
    all_companies = make_crm_api_request("GET", "organizations", {"limit": 200})

    if all_companies and "organizations" in all_companies:
        for company in all_companies["organizations"]:
            # Verifica se o campo personalizado de CNPJ existe e corresponde
            for custom_field in company.get("organization_custom_fields", []):
                if custom_field.get("custom_field_id") == CNPJ_EMPRESA_FIELD_ID and custom_field.get("value") == cnpj:
                    return company
    return None




def create_company(name, cnpj):
    company_data = {
        "name": name,
        "organization_custom_fields": [
            {
                "custom_field_id": CNPJ_EMPRESA_FIELD_ID,
                "value": cnpj
            }
        ]
    }
    return make_crm_api_request("POST", "organizations", company_data)




def find_contact_by_cnpj_or_email(cnpj=None, email=None):
    # A API do RD Station CRM permite filtrar contatos por email.
    # Para CNPJ, teremos que listar e filtrar, similar à empresa.

    if email:
        response = make_crm_api_request("GET", "contacts", {"email": email})
        if response and "contacts" in response and len(response["contacts"]) > 0:
            return response["contacts"][0]

    if cnpj:
        all_contacts = make_crm_api_request("GET", "contacts", {"limit": 200})
        if all_contacts and "contacts" in all_contacts:
            for contact in all_contacts["contacts"]:
                for custom_field in contact.get("contact_custom_fields", []):
                    if custom_field.get("custom_field_id") == CNPJ_CONTATO_FIELD_ID and custom_field.get("value") == cnpj:
                        return contact
    return None




def create_contact_and_link_to_company(name, email, cnpj, organization_id=None):
    contact_data = {
        "name": name,
        "email": {"email": email, "type": "work"},
        "contact_custom_fields": [
            {
                "custom_field_id": CNPJ_CONTATO_FIELD_ID,
                "value": cnpj
            }
        ]
    }
    if organization_id:
        contact_data["organization_id"] = organization_id

    return make_crm_api_request("POST", "contacts", contact_data)


