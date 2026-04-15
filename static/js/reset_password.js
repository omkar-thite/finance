import { parseApiError } from './auth.js';

const RESET_PASSWORD_FORM_ID = 'resetPasswordForm';
const MESSAGE_ELEMENT_ID = 'resetPasswordMessage';

function getMessageElement() {
    return document.getElementById(MESSAGE_ELEMENT_ID);
}

function setMessage(message, kind = 'error') {
    const messageElement = getMessageElement();
    if (!messageElement) return;

    messageElement.textContent = message;
    messageElement.className = `auth-message`;
    if (message) {
        messageElement.classList.add(kind === 'success' ? 'is-success' : 'is-error');
    }
}

function getTokenFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get('token');
}

function validatePasswordMatch(password, confirmPassword) {
    if (password !== confirmPassword) {
        setMessage('Passwords do not match.');
        return false;
    }
    return true;
}

function disableForm(disabled) {
    const form = document.getElementById(RESET_PASSWORD_FORM_ID);
    if (!form) return;

    const submitButton = form.querySelector('button[type="submit"]');
    const inputs = form.querySelectorAll('input');

    inputs.forEach(input => {
        input.disabled = disabled;
    });

    if (submitButton) {
        submitButton.disabled = disabled;
    }
}

function initializeForm() {
    const token = getTokenFromUrl();

    if (!token) {
        setMessage('No reset token found. Please check your email link.', 'error');
        disableForm(true);
        return;
    }

    const form = document.getElementById(RESET_PASSWORD_FORM_ID);
    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    }
}

async function handleFormSubmit(event) {
    event.preventDefault();

    const token = getTokenFromUrl();
    if (!token) {
        setMessage('No reset token found. Please request a new reset link.', 'error');
        return;
    }

    const password = document.getElementById('resetPasswordNew').value;
    const confirmPassword = document.getElementById('resetPasswordConfirm').value;

    // Validate passwords match
    if (!validatePasswordMatch(password, confirmPassword)) {
        return;
    }

    setMessage('');
    disableForm(true);

    try {
        const response = await fetch('/api/users/reset-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                token,
                new_password: password,
            }),
        });

        if (!response.ok) {
            const data = await response.json();
            const errorMessage = parseApiError(data, 'Failed to reset password. Please try again.');
            setMessage(errorMessage, 'error');
            disableForm(false);
            return;
        }

        setMessage('Password reset successfully! Redirecting to login...', 'success');
        setTimeout(() => {
            window.location.assign('/login');
        }, 1500);
    } catch (error) {
        setMessage('An error occurred. Please try again.', 'error');
        disableForm(false);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initializeForm);
