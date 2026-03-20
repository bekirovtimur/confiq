// Confiq JavaScript

// Notification Manager
class NotificationManager {
    static show(message, type = 'info', duration = 5000) {
        const alertContainer = document.createElement('div');
        alertContainer.className = 'position-fixed top-0 end-0 p-3';
        alertContainer.style.zIndex = '1060';
        
        const alertElement = document.createElement('div');
        alertElement.className = `alert alert-${type} alert-dismissible fade show`;
        alertElement.setAttribute('role', 'alert');
        
        const iconClass = this.getIconClass(type);
        
        alertElement.innerHTML = `
            <i class="bi ${iconClass}"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        alertContainer.appendChild(alertElement);
        document.body.appendChild(alertContainer);
        
        // Auto remove after duration
        setTimeout(() => {
            if (alertContainer.parentNode) {
                alertContainer.remove();
            }
        }, duration);
    }
    
    static getIconClass(type) {
        const icons = {
            'success': 'bi-check-circle',
            'danger': 'bi-exclamation-triangle',
            'warning': 'bi-exclamation-circle',
            'info': 'bi-info-circle'
        };
        return icons[type] || icons.info;
    }
}

// Form Validation
class FormValidator {
    static validateRequired(input) {
        const value = input.value.trim();
        if (!value) {
            this.setError(input, 'Это поле обязательно для заполнения');
            return false;
        }
        this.clearError(input);
        return true;
    }
    
    static validateMinLength(input, minLength) {
        const value = input.value.trim();
        if (value.length < minLength) {
            this.setError(input, `Минимальная длина: ${minLength} символов`);
            return false;
        }
        this.clearError(input);
        return true;
    }
    
    static validateEmail(input) {
        const email = input.value.trim();
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            this.setError(input, 'Введите корректный email адрес');
            return false;
        }
        this.clearError(input);
        return true;
    }
    
    static setError(input, message) {
        input.classList.add('is-invalid');
        input.classList.remove('is-valid');
        
        // Remove existing error message
        const existingError = input.parentNode.querySelector('.invalid-feedback');
        if (existingError) {
            existingError.remove();
        }
        
        // Add new error message
        const errorDiv = document.createElement('div');
        errorDiv.className = 'invalid-feedback';
        errorDiv.textContent = message;
        input.parentNode.appendChild(errorDiv);
    }
    
    static clearError(input) {
        input.classList.remove('is-invalid');
        const errorDiv = input.parentNode.querySelector('.invalid-feedback');
        if (errorDiv) {
            errorDiv.remove();
        }
    }
}

// Loading States
class LoadingManager {
    static setLoading(button, loading = true) {
        if (loading) {
            button.disabled = true;
            const originalText = button.innerHTML;
            button.setAttribute('data-original-text', originalText);
            button.innerHTML = `
                <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                Загрузка...
            `;
        } else {
            button.disabled = false;
            const originalText = button.getAttribute('data-original-text');
            if (originalText) {
                button.innerHTML = originalText;
            }
        }
    }
}

// Copy to Clipboard
class ClipboardManager {
    static async copy(text) {
        try {
            await navigator.clipboard.writeText(text);
            NotificationManager.show('Скопировано в буфер обмена!', 'success', 2000);
            return true;
        } catch (err) {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.opacity = '0';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            
            try {
                document.execCommand('copy');
                NotificationManager.show('Скопировано в буфер обмена!', 'success', 2000);
                return true;
            } catch (err) {
                NotificationManager.show('Ошибка копирования', 'danger');
                return false;
            } finally {
                document.body.removeChild(textArea);
            }
        }
    }
}

// Auto-hide alerts
function autoHideAlerts() {
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            // Check if bootstrap is available
            if (typeof bootstrap !== 'undefined' && bootstrap.Alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            } else {
                // Fallback: remove alert manually
                alert.classList.remove('show');
                setTimeout(() => {
                    if (alert.parentNode) {
                        alert.parentNode.removeChild(alert);
                    }
                }, 150);
            }
        }, 5000);
    });
}

// Initialize tooltips
function initTooltips() {
    if (typeof bootstrap === 'undefined') return;
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Initialize popovers
function initPopovers() {
    if (typeof bootstrap === 'undefined') return;
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
}

// Form submission with loading state
function handleFormSubmission() {
    const forms = document.querySelectorAll('form[data-loading="true"]');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitButton = form.querySelector('button[type="submit"]');
            if (submitButton) {
                LoadingManager.setLoading(submitButton, true);
            }
        });
    });
}

// Copy configuration content
function copyConfig(configContent, button) {
    ClipboardManager.copy(configContent);
    
    // Visual feedback
    const originalText = button.innerHTML;
    button.innerHTML = '<i class="bi bi-check"></i> Скопировано!';
    button.classList.remove('btn-outline-secondary');
    button.classList.add('btn-success');
    
    setTimeout(() => {
        button.innerHTML = originalText;
        button.classList.remove('btn-success');
        button.classList.add('btn-outline-secondary');
    }, 2000);
}

// Auto-refresh functionality
class AutoRefresh {
    constructor(interval = 30000) {
        this.interval = interval;
        this.isActive = false;
        this.intervalId = null;
    }
    
    start(callback) {
        if (!this.isActive) {
            this.isActive = true;
            this.intervalId = setInterval(callback, this.interval);
        }
    }
    
    stop() {
        if (this.isActive && this.intervalId) {
            clearInterval(this.intervalId);
            this.isActive = false;
            this.intervalId = null;
        }
    }
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap components
    initTooltips();
    initPopovers();
    
    // Auto-hide alerts
    autoHideAlerts();
    
    // Handle form submissions
    handleFormSubmission();
    
    // Add fade-in animation to cards
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
        card.classList.add('fade-in');
    });
});

// Global error handler
window.addEventListener('error', function(e) {
    console.error('Global error:', e.error);
    NotificationManager.show('Произошла ошибка. Попробуйте обновить страницу.', 'danger');
});

// Export for global usage
window.WarpManager = {
    NotificationManager,
    FormValidator,
    LoadingManager,
    ClipboardManager,
    AutoRefresh,
    copyConfig
};