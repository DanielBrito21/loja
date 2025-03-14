from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import urllib.parse

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'  # Necessário para o carrinho (session)
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Função para conectar ao banco de dados
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Inicializa o banco de dados
def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        descricao TEXT,
        preco REAL NOT NULL,
        preco_promocional REAL,
        estoque INTEGER NOT NULL,
        categoria TEXT NOT NULL,
        imagem TEXT,
        imagens_adicionais TEXT
    )''')
    conn.commit()
    conn.close()

# Função para obter categorias (usada em todas as rotas)
def get_categorias():
    conn = get_db_connection()
    categorias = conn.execute('SELECT DISTINCT categoria FROM produtos').fetchall()
    conn.close()
    return categorias

# Página inicial com filtros e busca
@app.route('/', methods=['GET'])
def index():
    conn = get_db_connection()
    query = 'SELECT * FROM produtos WHERE estoque > 0'
    params = []

    # Filtro por categoria
    categoria = request.args.get('categoria')
    if categoria and categoria != 'todos':
        query += ' AND categoria = ?'
        params.append(categoria)

    # Busca por nome
    busca = request.args.get('busca')
    if busca:
        query += ' AND nome LIKE ?'
        params.append(f'%{busca}%')

    # Filtro por preço
    preco_min = request.args.get('preco_min', type=float)
    preco_max = request.args.get('preco_max', type=float)
    if preco_min:
        query += ' AND preco >= ?'
        params.append(preco_min)
    if preco_max:
        query += ' AND preco <= ?'
        params.append(preco_max)

    produtos = conn.execute(query, params).fetchall()
    categorias = get_categorias()
    conn.close()

    # Defina a categoria selecionada para o template
    selected_categoria = categoria if categoria != 'todos' else None
    return render_template('index.html', produtos=produtos, categorias=categorias, selected_categoria=selected_categoria)

# Página de detalhes do produto
@app.route('/produto/<int:id>')
def produto_detalhes(id):
    conn = get_db_connection()
    produto = conn.execute('SELECT * FROM produtos WHERE id = ?', (id,)).fetchone()
    categorias = get_categorias()
    conn.close()
    return render_template('detalhes.html', produto=produto, categorias=categorias)

# Adicionar ao carrinho
@app.route('/adicionar_carrinho/<int:id>', methods=['POST'])
def adicionar_carrinho(id):
    if 'carrinho' not in session:
        session['carrinho'] = {}
    quantidade = int(request.form.get('quantidade', 1))
    conn = get_db_connection()
    produto = conn.execute('SELECT * FROM produtos WHERE id = ?', (id,)).fetchone()
    if produto and quantidade <= produto['estoque']:
        session['carrinho'][str(id)] = session['carrinho'].get(str(id), 0) + quantidade
        session.modified = True
        flash('Produto adicionado ao carrinho com sucesso!', 'success')
    conn.close()
    return redirect(url_for('index'))

# Visualizar carrinho
@app.route('/carrinho')
def carrinho():
    conn = get_db_connection()
    carrinho_itens = []
    total = 0
    if 'carrinho' in session:
        for id, quantidade in session['carrinho'].items():
            produto = conn.execute('SELECT * FROM produtos WHERE id = ?', (id,)).fetchone()
            if produto:
                preco = produto['preco_promocional'] if produto['preco_promocional'] else produto['preco']
                subtotal = preco * quantidade
                total += subtotal
                carrinho_itens.append({
                    'produto': dict(produto),
                    'quantidade': quantidade,
                    'subtotal': subtotal,
                    'preco_unitario': preco
                })
                print(f"Item no carrinho: ID={id}, Quantidade={quantidade}, Produto={produto['nome']}")
    categorias = get_categorias()
    conn.close()
    print(f"Tipo de carrinho_itens: {type(carrinho_itens)}, Conteúdo: {carrinho_itens}")
    return render_template('carrinho.html', carrinho_itens=carrinho_itens, total=total, categorias=categorias)

# Remover item do carrinho
@app.route('/remover_carrinho/<int:id>', methods=['POST'])
def remover_carrinho(id):
    if 'carrinho' in session and str(id) in session['carrinho']:
        del session['carrinho'][str(id)]
        session.modified = True
        flash('Item removido do carrinho!', 'success')
    return redirect(url_for('carrinho'))

# Finalizar compra via WhatsApp
@app.route('/finalizar_compra')
def finalizar_compra():
    if 'carrinho' not in session or not session['carrinho']:
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    mensagem = "Olá, quero comprar:\n"
    total = 0
    for id, quantidade in session['carrinho'].items():
        produto = conn.execute('SELECT * FROM produtos WHERE id = ?', (id,)).fetchone()
        preco = produto['preco_promocional'] if produto['preco_promocional'] else produto['preco']
        subtotal = preco * quantidade
        total += subtotal
        mensagem += f"- {quantidade}x {produto['nome']} (R$ {subtotal:.2f})\n"
    mensagem += f"Total: R$ {total:.2f}"
    conn.close()
    
    # Codificar a mensagem para ser segura em URLs
    mensagem_codificada = urllib.parse.quote(mensagem)
    
    session.pop('carrinho', None)  # Limpa o carrinho após finalizar
    return redirect(f"https://wa.me/5521983250345?text={mensagem_codificada}")

# Administração
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    conn = get_db_connection()
    
    if request.method == 'POST' and 'nome' in request.form:
        nome = request.form['nome']
        descricao = request.form['descricao']
        preco = float(request.form['preco'])
        preco_promocional = float(request.form['preco_promocional']) if request.form['preco_promocional'] else None
        estoque = int(request.form['estoque'])
        categoria = request.form['categoria']
        imagem = request.files['imagem']  # Imagem principal
        imagens_adicionais = request.files.getlist('imagens_adicionais[]')  # Lista de imagens adicionais
        
        # Salvar a imagem principal
        if imagem:
            imagem_path = os.path.join(app.config['UPLOAD_FOLDER'], imagem.filename)
            imagem.save(imagem_path)
            imagem_nome = imagem.filename
        else:
            imagem_nome = None
        
        # Salvar as imagens adicionais
        imagens_adicionais_nomes = []
        for img in imagens_adicionais:
            if img:
                img_path = os.path.join(app.config['UPLOAD_FOLDER'], img.filename)
                img.save(img_path)
                imagens_adicionais_nomes.append(img.filename)
        
        # Converter a lista de nomes em uma string separada por vírgulas
        imagens_adicionais_str = ','.join(imagens_adicionais_nomes) if imagens_adicionais_nomes else None
        
        # Inserir no banco de dados, incluindo imagens_adicionais
        conn.execute('INSERT INTO produtos (nome, descricao, preco, preco_promocional, estoque, categoria, imagem, imagens_adicionais) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                     (nome, descricao, preco, preco_promocional, estoque, categoria, imagem_nome, imagens_adicionais_str))
        conn.commit()
    
    if request.method == 'POST' and 'delete_id' in request.form:
        delete_id = request.form['delete_id']
        conn.execute('DELETE FROM produtos WHERE id = ?', (delete_id,))
        conn.commit()
    
    produtos = conn.execute('SELECT * FROM produtos').fetchall()
    categorias = get_categorias()
    conn.close()
    return render_template('admin.html', produtos=produtos, categorias=categorias)

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    init_db()
    app.run(debug=True)