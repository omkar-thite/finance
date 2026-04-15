import { parseApiError } from './auth.js';

const FORGOT_PASSWORD_FORM_ID = 'forgotPasswordForm';
const MESSAGE_ELEMENT_ID = 'forgotPasswordMessage';

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

function setFormBusy(busy) {
    const form = document.getElementById(FORGOT_PASSWORD_FORM_ID);
    if (!form) return;

    const submitButton = form.querySelector('button[type="submit"]');
    const input = form.querySelector('input[type="email"]');

    if (input) {
        input.disabled = busy;
    }

    if (submitButton) {
        submitButton.disabled = busy;
        submitButton.textContent = busy ? 'Sending...' : 'Send Reset Link';
    }
}

async function handleFormSubmit(event) {
    event.preventDefault();

    const emailInput = document.getElementById('forgotPasswordEmail');
    const email = emailInput.value.trim();

    if (!email) {
        setMessage('Please enter your email address.', 'error');
        return;
    }

    setMessage('');
    setFormBusy(true);

    try {
        const response = await fetch('/api/users/forgot-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email }),
        });

        // 202 Accepted is the expected response for forgot password
        if (response.status === 202 || response.ok) {
            setMessage(
                'If an account exists with this email, you will receive a password reset link shortly.',
                'success'
            );
            emailInput.value = '';
            return;
        }

        const data = await response.json();
        const errorMessage = parseApiError(data, 'Unable to process your request. Please try again.');
        setMessage(errorMessage, 'error');
    } catch (error) {
        setMessage('An error occurred. Please try again.', 'error');
    } finally {
        setFormBusy(false);
    }
}

function initializeForm() {
    const form = document.getElementById(FORGOT_PASSWORD_FORM_ID);
    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initializeForm);
