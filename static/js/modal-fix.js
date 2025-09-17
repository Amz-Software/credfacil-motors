/**
 * Correção para conflitos de hover em modais
 */
document.addEventListener('DOMContentLoaded', function() {
    // Desabilitar hover effects quando modal está aberto
    const modals = document.querySelectorAll('.modal');
    
    modals.forEach(modal => {
        modal.addEventListener('show.bs.modal', function() {
            // Adicionar classe para desabilitar hover
            document.body.classList.add('modal-hover-disabled');
        });
        
        modal.addEventListener('hidden.bs.modal', function() {
            // Remover classe para reabilitar hover
            document.body.classList.remove('modal-hover-disabled');
        });
    });
    
    // Prevenir conflitos de z-index
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList') {
                const modals = document.querySelectorAll('.modal');
                modals.forEach(modal => {
                    if (!modal.style.zIndex || modal.style.zIndex < 1055) {
                        modal.style.zIndex = '1055';
                    }
                });
                
                const backdrops = document.querySelectorAll('.modal-backdrop');
                backdrops.forEach(backdrop => {
                    if (!backdrop.style.zIndex || backdrop.style.zIndex < 1050) {
                        backdrop.style.zIndex = '1050';
                    }
                });
            }
        });
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
});
