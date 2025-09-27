/**
 * Correção completa para modais - CredFácil
 * Resolve todos os conflitos de CSS e JavaScript que podem causar bugs nos modais
 */
document.addEventListener('DOMContentLoaded', function() {
    
    // Função para garantir z-index correto
    function ensureModalZIndex() {
        const modals = document.querySelectorAll('.modal');
        const backdrops = document.querySelectorAll('.modal-backdrop');
        
        modals.forEach((modal, index) => {
            modal.style.zIndex = 1055 + index;
        });
        
        backdrops.forEach((backdrop, index) => {
            backdrop.style.zIndex = 1050 + index;
        });
    }
    
    // Função para desabilitar hover effects quando modal está aberto
    function disableHoverEffects() {
        document.body.classList.add('modal-open');
        
        // Desabilitar hover de tabelas
        const tableRows = document.querySelectorAll('.table tbody tr');
        tableRows.forEach(row => {
            row.style.pointerEvents = 'none';
        });
        
        // Desabilitar hover de cards
        const cards = document.querySelectorAll('.card');
        cards.forEach(card => {
            card.style.transform = 'none';
            card.style.boxShadow = '';
        });
    }
    
    // Função para reabilitar hover effects quando modal fecha
    function enableHoverEffects() {
        document.body.classList.remove('modal-open');
        
        // Reabilitar hover de tabelas
        const tableRows = document.querySelectorAll('.table tbody tr');
        tableRows.forEach(row => {
            row.style.pointerEvents = 'auto';
        });
        
        // Reabilitar hover de cards
        const cards = document.querySelectorAll('.card');
        cards.forEach(card => {
            card.style.transform = '';
            card.style.boxShadow = '';
        });
    }
    
    // Configurar eventos para todos os modais existentes
    function setupModalEvents() {
        const modals = document.querySelectorAll('.modal');
        
        modals.forEach(modal => {
            // Remover listeners existentes para evitar duplicação
            modal.removeEventListener('show.bs.modal', handleModalShow);
            modal.removeEventListener('shown.bs.modal', handleModalShown);
            modal.removeEventListener('hide.bs.modal', handleModalHide);
            modal.removeEventListener('hidden.bs.modal', handleModalHidden);
            
            // Adicionar novos listeners
            modal.addEventListener('show.bs.modal', handleModalShow);
            modal.addEventListener('shown.bs.modal', handleModalShown);
            modal.addEventListener('hide.bs.modal', handleModalHide);
            modal.addEventListener('hidden.bs.modal', handleModalHidden);
        });
    }
    
    // Handlers para eventos de modal
    function handleModalShow(event) {
        console.log('Modal show event triggered');
        disableHoverEffects();
        ensureModalZIndex();
        
        // Garantir que o backdrop seja criado corretamente
        setTimeout(() => {
            ensureModalZIndex();
        }, 50);
    }
    
    function handleModalShown(event) {
        console.log('Modal shown event triggered');
        ensureModalZIndex();
        
        // Focar no primeiro input do modal
        const modal = event.target;
        const firstInput = modal.querySelector('input, select, textarea');
        if (firstInput) {
            firstInput.focus();
        }
    }
    
    function handleModalHide(event) {
        console.log('Modal hide event triggered');
        // Não reabilitar ainda, aguardar hidden
    }
    
    function handleModalHidden(event) {
        console.log('Modal hidden event triggered');
        enableHoverEffects();
        ensureModalZIndex();
    }
    
    // Observer para novos modais dinamicamente criados
    const observer = new MutationObserver(function(mutations) {
        let shouldSetup = false;
        
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList') {
                mutation.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1) { // Element node
                        if (node.classList && node.classList.contains('modal')) {
                            shouldSetup = true;
                        } else if (node.querySelector && node.querySelector('.modal')) {
                            shouldSetup = true;
                        }
                    }
                });
            }
        });
        
        if (shouldSetup) {
            setTimeout(() => {
                setupModalEvents();
                ensureModalZIndex();
            }, 100);
        }
    });
    
    // Inicializar
    setupModalEvents();
    ensureModalZIndex();
    
    // Observar mudanças no DOM
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // Garantir z-index correto em intervalos regulares (fallback)
    setInterval(ensureModalZIndex, 1000);
    
    // Prevenir scroll do body quando modal está aberto
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            const openModals = document.querySelectorAll('.modal.show');
            if (openModals.length > 0) {
                const lastModal = openModals[openModals.length - 1];
                const modalInstance = bootstrap.Modal.getInstance(lastModal);
                if (modalInstance) {
                    modalInstance.hide();
                }
            }
        }
    });
    
    // Correção para Select2 em modais
    document.addEventListener('select2:open', function(event) {
        const select2Dropdown = event.target.nextElementSibling;
        if (select2Dropdown && select2Dropdown.classList.contains('select2-dropdown')) {
            select2Dropdown.style.zIndex = '1056';
        }
    });
    
    // Correção para tooltips em modais
    document.addEventListener('shown.bs.tooltip', function(event) {
        const tooltip = event.target.nextElementSibling;
        if (tooltip && tooltip.classList.contains('tooltip')) {
            tooltip.style.zIndex = '1057';
        }
    });
    
    console.log('Modal fix script loaded and initialized');
});
