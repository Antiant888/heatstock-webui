// Main JavaScript for HK Stock News Dashboard

// Mobile menu toggle
document.addEventListener('DOMContentLoaded', function() {
    const mobileMenuButton = document.querySelector('.mobile-menu-button');
    const mobileMenu = document.querySelector('.mobile-menu');

    if (mobileMenuButton && mobileMenu) {
        mobileMenuButton.addEventListener('click', function() {
            mobileMenu.classList.toggle('active');
        });
    }

    // Close mobile menu when clicking outside
    document.addEventListener('click', function(event) {
        if (!event.target.closest('.mobile-menu') && !event.target.closest('.mobile-menu-button')) {
            if (mobileMenu) {
                mobileMenu.classList.remove('active');
            }
        }
    });
});

// Utility function to format numbers
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

// Utility function to format dates
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Utility function to debounce input
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Relative time calculation for "Last Updated" card
function updateRelativeTime() {
    const relativeTimeElement = document.getElementById('relative-time');
    if (!relativeTimeElement) return;
    
    const timestamp = parseInt(relativeTimeElement.dataset.timestamp);
    if (isNaN(timestamp)) return;
    
    const now = Date.now();
    const diff = now - timestamp;
    
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    let relativeTime = '';
    
    if (days > 0) {
        relativeTime = days + ' day' + (days > 1 ? 's' : '') + ' ago';
    } else if (hours > 0) {
        relativeTime = hours + ' hour' + (hours > 1 ? 's' : '') + ' ago';
    } else if (minutes > 0) {
        relativeTime = minutes + ' min' + (minutes > 1 ? 's' : '') + ' ago';
    } else {
        relativeTime = 'Just now';
    }
    
    relativeTimeElement.textContent = relativeTime;
}

// Initialize relative time on page load
document.addEventListener('DOMContentLoaded', function() {
    updateRelativeTime();
    // Update every minute
    setInterval(updateRelativeTime, 60000);
});

// Export functions for use in other scripts
window.utils = {
    formatNumber,
    formatDate,
    debounce
};
