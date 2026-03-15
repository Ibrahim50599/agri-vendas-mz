
{% extends "base.html" %}

{% block title %}Produtos - AGRI.vendasMz{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <div>
        <h2 class="mb-1"><i class="fas fa-store text-success me-2"></i> Marketplace Agrícola</h2>
        <p class="text-muted mb-0">Encontre os melhores produtos agrícolas de Moçambique</p>
    </div>
    <div class="d-flex gap-2">
        <span class="badge bg-success fs-6">{{ produtos|length }} produtos disponíveis</span>
    </div>
</div>

<!-- Filtros Avançados -->
<div class="card shadow-sm mb-4">
    <div class="card-header bg-gradient" style="background: linear-gradient(135deg, #E8F5E8 0%, #F1F8E9 100%);">
        <h5 class="mb-0"><i class="fas fa-filter text-success me-2"></i> Filtros Inteligentes</h5>
    </div>
    <div class="card-body">
        <form method="GET" class="row g-3">
            <div class="col-md-3">
                <label class="form-label fw-semibold">Categoria</label>
                <select class="form-select form-select-lg" name="categoria">
                    <option value="">Todas as categorias</option>
                    <option value="Cereais">Cereais</option>
                    <option value="Legumes">Legumes</option>
                    <option value="Frutas">Frutas</option>
                    <option value="Tubérculos">Tubérculos</option>
                    <option value="Sementes">Sementes</option>
                    <option value="Fertilizantes">Fertilizantes</option>
                    <option value="Equipamentos">Equipamentos</option>
                </select>
            </div>

            <div class="col-md-3">
                <label class="form-label fw-semibold">Preço Máximo</label>
                <div class="input-group input-group-lg">
                    <span class="input-group-text">MT</span>
                    <input type="number" class="form-control" name="preco_max" placeholder="0.00" step="0.01">
                </div>
            </div>

            <div class="col-md-3">
                <label class="form-label fw-semibold">Localização</label>
                <input type="text" class="form-control form-control-lg" name="regiao" placeholder="Ex: Maputo, Gaza, Inhambane">
            </div>

            <div class="col-md-3 d-flex align-items-end">
                <div class="w-100">
                    <button type="submit" class="btn btn-success btn-lg w-100 mb-2">
                        <i class="fas fa-search me-2"></i> Buscar Produtos
                    </button>
                    <a href="{{ url_for('listar_produtos') }}" class="btn btn-outline-secondary w-100">
                        <i class="fas fa-refresh me-2"></i> Limpar Filtros
                    </a>
                </div>
            </div>
        </form>
    </div>
</div>

<!-- Grid de Produtos -->
{% if produtos %}
    <div class="row g-4">
        {% for produto in produtos %}
            <div class="col-xl-3 col-lg-4 col-md-6">
                <div class="card product-card h-100 shadow-sm">
                    <!-- Imagem do Produto -->
                    <div class="position-relative overflow-hidden" style="height: 220px;">
                        {% if produto[6] %}
                            <img src="{{ url_for('static', filename=produto[6]) }}"
                                 class="card-img-top w-100 h-100"
                                 style="object-fit: cover; transition: transform 0.3s ease;"
                                 onmouseover="this.style.transform='scale(1.05)'"
                                 onmouseout="this.style.transform='scale(1)'">
                        {% else %}
                            <div class="w-100 h-100 bg-light d-flex align-items-center justify-content-center">
                                <div class="text-center">
                                    <i class="fas fa-image fa-3x text-muted mb-2"></i>
                                    <p class="text-muted mb-0">Sem imagem</p>
                                </div>
                            </div>
                        {% endif %}

                        <!-- Badge de Categoria -->
                        {% if produto[7] %}
                            <span class="position-absolute top-0 start-0 m-2 badge bg-success fs-6">
                                {{ produto[7] }}
                            </span>
                        {% endif %}
                    </div>

                    <!-- Conteúdo do Card -->
                    <div class="card-body d-flex flex-column">
                        <h6 class="card-title fw-bold text-dark mb-2" style="font-size: 17px;">
                            {{ produto[2] }}
                        </h6>

                        <div class="mb-3">
                            <span class="text-success fw-bold fs-4">{{ "%.2f"|format(produto[3]) }} MT</span>
                        </div>

                        <p class="card-text text-muted flex-grow-1" style="font-size: 14px; line-height: 1.5;">
                            {{ produto[4][:120] }}{% if produto[4]|length > 120 %}...{% endif %}
                        </p>

                        <!-- Informações do Vendedor -->
                        <div class="border-top pt-3 mt-auto">
                            <div class="d-flex align-items-center mb-2">
                                <i class="fas fa-map-marker-alt text-danger me-2"></i>
                                <small class="text-muted fw-medium">{{ produto[5] }}</small>
                            </div>

                            <div class="d-flex align-items-center mb-3">
                                <i class="fas fa-user-circle text-primary me-2"></i>
                                <small class="text-muted fw-medium">{{ produto[9] }}</small>
                            </div>
                        </div>
                    </div>

                    <!-- Ações -->
                    <div class="card-footer bg-white border-top">
                        <div class="row g-2">
                            <div class="col-6">
                                <button class="btn btn-outline-primary btn-sm w-100" onclick="quickView({{ produto[0] }})">
                                    <i class="fas fa-eye me-1"></i> Ver
                                </button>
                            </div>
                            <div class="col-6">
                                <a href="{{ url_for('contato_whatsapp', vendedor_id=produto[1]) }}"
                                   class="btn btn-success btn-sm w-100">
                                    <i class="fab fa-whatsapp me-1"></i> Contactar
                                </a>
                            </div>
                        </div>
                        <div class="mt-2 text-center">
                            <button class="btn btn-link btn-sm text-muted p-0" onclick="toggleFavorite({{ produto[0] }})">
                                <i class="far fa-heart me-1" id="heart-{{ produto[0] }}"></i>
                                <small>Favoritar</small>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        {% endfor %}
    </div>

    <!-- Paginação ou Load More -->
    <div class="text-center mt-5">
        <button class="btn btn-outline-success btn-lg px-4" id="loadMoreBtn" onclick="loadMoreProducts()">
            <i class="fas fa-plus-circle me-2"></i> Carregar Mais Produtos
        </button>
        <div id="loadingSpinner" class="d-none mt-3">
            <div class="spinner-border text-success" role="status">
                <span class="visually-hidden">Carregando...</span>
            </div>
        </div>
    </div>

{% else %}
    <!-- Estado Vazio -->
    <div class="text-center py-5">
        <div class="mb-4">
            <i class="fas fa-search fa-4x text-muted opacity-50"></i>
        </div>
        <h4 class="text-muted mb-3">Nenhum produto encontrado</h4>
        <p class="text-muted mb-4">Tente ajustar os filtros ou explore outras categorias.</p>
        <div class="d-flex justify-content-center gap-3">
            <a href="{{ url_for('listar_produtos') }}" class="btn btn-success btn-lg">
                <i class="fas fa-refresh me-2"></i> Ver Todos os Produtos
            </a>
            {% if session.user_type in ['vendedor', 'admin'] %}
                <a href="{{ url_for('publicar_produto') }}" class="btn btn-outline-success btn-lg">
                    <i class="fas fa-plus me-2"></i> Publicar Produto
                </a>
            {% endif %}
        </div>
    </div>
{% endif %}

<!-- Quick View Modal -->
<div class="modal fade" id="quickViewModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="quickViewTitle">Detalhes do Produto</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body" id="quickViewBody">
                <!-- Content will be loaded here -->
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fechar</button>
                <button type="button" class="btn btn-success" id="contactBtn">
                    <i class="fab fa-whatsapp me-2"></i> Contactar Vendedor
                </button>
            </div>
        </div>
    </div>
</div>

<!-- Estatísticas do Marketplace -->
<div class="card mt-5 bg-gradient" style="background: linear-gradient(135deg, #E8F5E8 0%, #F1F8E9 100%);">
    <div class="card-body text-center py-4">
        <div class="row">
            <div class="col-md-4">
                <h3 class="text-success fw-bold">{{ produtos|length }}+</h3>
                <p class="mb-0 fw-semibold">Produtos Disponíveis</p>
            </div>
            <div class="col-md-4">
                <h3 class="text-success fw-bold">100+</h3>
                <p class="mb-0 fw-semibold">Vendedores Ativos</p>
            </div>
            <div class="col-md-4">
                <h3 class="text-success fw-bold">11</h3>
                <p class="mb-0 fw-semibold">Províncias Cobertas</p>
            </div>
        </div>
    </div>
</div>

<script>
// Product interaction functions
let currentPage = 1;
const productsPerPage = 12;
let favorites = JSON.parse(localStorage.getItem('favorites') || '[]');

function loadMoreProducts() {
    const btn = document.getElementById('loadMoreBtn');
    const spinner = document.getElementById('loadingSpinner');

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Carregando...';
    spinner.classList.remove('d-none');

    // Simulate loading more products
    setTimeout(() => {
        currentPage++;
        // In a real app, this would make an AJAX call to load more products
        // For now, we'll just hide the button after a few loads
        if (currentPage >= 3) {
            btn.style.display = 'none';
        }

        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-plus-circle me-2"></i> Carregar Mais Produtos';
        spinner.classList.add('d-none');

        // Show success message
        showToast('Mais produtos carregados!', 'success');
    }, 1500);
}

function quickView(productId) {
    // Find product data (in real app, this would be an AJAX call)
    const products = {{ produtos|tojson }};
    const product = products.find(p => p[0] === productId);

    if (product) {
        document.getElementById('quickViewTitle').textContent = product[2];

        const body = document.getElementById('quickViewBody');
        body.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    ${product[6] ?
                        `<img src="/static/${product[6]}" class="img-fluid rounded" alt="${product[2]}">` :
                        `<div class="bg-light d-flex align-items-center justify-content-center rounded" style="height: 300px;">
                            <i class="fas fa-image fa-3x text-muted"></i>
                        </div>`
                    }
                </div>
                <div class="col-md-6">
                    <h4 class="text-success">${product[2]}</h4>
                    <h3 class="text-success fw-bold mb-3">${product[3].toFixed(2)} MT</h3>
                    <p class="mb-3">${product[4]}</p>
                    <div class="mb-3">
                        <strong>Categoria:</strong> ${product[7] || 'N/A'}<br>
                        <strong>Localização:</strong> ${product[5]}<br>
                        <strong>Vendedor:</strong> ${product[9]}
                    </div>
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>
                        Entre em contato diretamente com o vendedor para mais detalhes e negociação.
                    </div>
                </div>
            </div>
        `;

        document.getElementById('contactBtn').onclick = () => {
            window.open(`https://wa.me/258${product[10] || '878312890'}?text=Olá! Vi seu produto "${product[2]}" no AGRI.vendasMz e gostaria de mais informações.`, '_blank');
        };

        new bootstrap.Modal(document.getElementById('quickViewModal')).show();
    }
}

function toggleFavorite(productId) {
    const heartIcon = document.getElementById(`heart-${productId}`);

    if (favorites.includes(productId)) {
        favorites = favorites.filter(id => id !== productId);
        heartIcon.className = 'far fa-heart me-1';
        showToast('Removido dos favoritos', 'info');
    } else {
        favorites.push(productId);
        heartIcon.className = 'fas fa-heart me-1 text-danger';
        showToast('Adicionado aos favoritos!', 'success');
    }

    localStorage.setItem('favorites', JSON.stringify(favorites));
}

// Initialize favorites on page load
document.addEventListener('DOMContentLoaded', function() {
    favorites.forEach(id => {
        const heartIcon = document.getElementById(`heart-${id}`);
        if (heartIcon) {
            heartIcon.className = 'fas fa-heart me-1 text-danger';
        }
    });
});

// Toast notification function
function showToast(message, type = 'info') {
    const toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
    toastContainer.innerHTML = `
        <div class="toast align-items-center text-white bg-${type} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;

    document.body.appendChild(toastContainer);
    const toast = new bootstrap.Toast(toastContainer.querySelector('.toast'));
    toast.show();

    setTimeout(() => {
        document.body.removeChild(toastContainer);
    }, 3000);
}

// Enhanced search with debouncing
let searchTimeout;
document.querySelector('input[name="regiao"]')?.addEventListener('input', function() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        // Auto-suggest locations
        console.log('Searching locations...');
    }, 500);
});
</script>
