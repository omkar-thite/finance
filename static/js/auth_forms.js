const AUTH_TOKEN_KEY = 'access_token';

function getMessageNode(formId) {
    return document.getElementById(`${formId}-message`);
}

function stringifyMessage(value) {
    if (value == null) {
        return '';
    }

    if (typeof value === 'string') {
        return value;
    }

    if (value instanceof Error) {
        return value.message;
    }

    if (Array.isArray(value)) {
        if (value.length > 0 && value.every((entry) => entry && typeof entry === 'object' && 'loc' in entry && 'msg' in entry)) {
            return value
                .map((entry) => {
                    const location = Array.isArray(entry.loc)
                        ? entry.loc.filter((part) => part !== 'body').join('.')
                        : '';
                    const message = String(entry.msg || '').trim();

                    if (location === 'email' && /email address/i.test(message)) {
                        return 'Email must be a valid email address. Example: user@example.com';
                    }

                    return message;
                })
                .filter(Boolean)
                .join(', ');
        }

        return value.map(stringifyMessage).filter(Boolean).join(', ');
    }

    if (typeof value === 'object') {
        if ('detail' in value) {
            return stringifyMessage(value.detail);
        }

        if ('message' in value) {
            return stringifyMessage(value.message);
        }

        if ('msg' in value) {
            return stringifyMessage(value.msg);
        }

        return Object.entries(value)
            .filter(([key]) => !['loc', 'input', 'ctx', 'type'].includes(key))
            .map(([, entry]) => stringifyMessage(entry))
            .filter(Boolean)
            .join(', ');
    }

    return String(value);
}

function setMessage(formId, message, kind = 'error') {
    const messageNode = getMessageNode(formId);
    if (!messageNode) {
        return;
    }

    messageNode.textContent = stringifyMessage(message);
    messageNode.classList.remove('is-error', 'is-success');
    if (message) {
        messageNode.classList.add(kind === 'success' ? 'is-success' : 'is-error');
    }
}

function setFormBusy(form, busy) {
    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) {
        submitButton.disabled = busy;
        submitButton.textContent = busy ? 'Please wait...' : submitButton.dataset.defaultLabel;
    }

    form.querySelectorAll('input, button').forEach((element) => {
        if (element.type !== 'submit') {
            element.disabled = busy;
        }
    });
}

function storeToken(token) {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
}

async function fetchCurrentUser(token) {
    const response = await fetch('/api/users/me', {
        headers: {
            Authorization: `Bearer ${token}`,
        },
    });

    if (!response.ok) {
        throw new Error('Unable to load current user.');
    }

    return response.json();
}

async function handleLogin(formData) {
    const email = String(formData.get('username') || '').trim();
    const password = String(formData.get('password') || '');

    if (!email || !password) {
        throw new Error('Email and password are required.');
    }

    const response = await fetch('/api/users/token', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({ username: email, password }),
    });

    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(stringifyMessage(payload.detail) || 'Sign in failed.');
    }

    storeToken(payload.access_token);
    const user = await fetchCurrentUser(payload.access_token);
    window.location.assign(user?.id ? `/users/${user.id}` : '/');
}

async function handleRegister(formData) {
    const username = String(formData.get('username') || '').trim();
    const email = String(formData.get('email') || formData.get('username') || '').trim();
    const phoneNo = String(formData.get('phone_no') || '').trim();
    const password = String(formData.get('password') || '');
    const confirmPassword = String(formData.get('confirm_password') || '');

    if (password !== confirmPassword) {
        throw new Error('Passwords do not match.');
    }

    const response = await fetch('/api/users/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            username,
            email,
            password,
            phone_no: phoneNo || null,            
        }),
    });

    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(stringifyMessage(payload.detail) || 'Account creation failed.');
    }

    const loginResponse = await fetch('/api/users/token', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({ username: email, password }),
    });

    const loginPayload = await loginResponse.json().catch(() => ({}));

    if (loginResponse.ok && loginPayload.access_token) {
        storeToken(loginPayload.access_token);
        const user = await fetchCurrentUser(loginPayload.access_token);
        window.location.assign(user?.id ? `/users/${user.id}` : '/');
        return;
    }

    sessionStorage.setItem('pending_login_email', email);
    window.location.assign('/login?registered=1');
}

function getRegisterPasswordElements() {
    return {
        emailInput: document.getElementById('register-email'),
        emailMessage: document.getElementById('register-email-hint'),
        passwordInput: document.getElementById('register-password'),
        confirmPasswordInput: document.getElementById('register-confirm-password'),
        matchMessage: document.getElementById('register-password-match'),
    };
}

function normalizeEmailValue(value) {
    return String(value || '').replace(/\s+/gu, '');
}

function isEmailFormatValid(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function updateEmailValidityState() {
    const { emailInput, emailMessage } = getRegisterPasswordElements();

    if (!emailInput) {
        return null;
    }

    const email = normalizeEmailValue(emailInput.value);
    if (emailInput.value !== email) {
        emailInput.value = email;
    }

    const hasValue = email.length > 0;
    const isValidEmail = !hasValue || isEmailFormatValid(email);
    const errorMessage = hasValue && !isValidEmail
        ? 'Email must be a valid email address'
        : '';

    emailInput.setCustomValidity(errorMessage);
    emailMessage.textContent = errorMessage;
    emailMessage.classList.toggle('is-error', Boolean(errorMessage));

    return isValidEmail;
}

function updatePasswordMatchState() {
    const { passwordInput, confirmPasswordInput, matchMessage } = getRegisterPasswordElements();

    if (!passwordInput || !confirmPasswordInput || !matchMessage) {
        return true;
    }

    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;
    const hasConfirmValue = confirmPassword.length > 0;
    const passwordsMatch = !hasConfirmValue || password === confirmPassword;

    confirmPasswordInput.setCustomValidity(passwordsMatch ? '' : 'Passwords do not match.');
    matchMessage.textContent = passwordsMatch ? '' : 'Passwords do not match.';
    matchMessage.classList.toggle('is-error', hasConfirmValue && !passwordsMatch);

    return passwordsMatch;
}

function prepareSubmitButton(form) {
    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton && !submitButton.dataset.defaultLabel) {
        submitButton.dataset.defaultLabel = submitButton.textContent.trim();
    }
}

function hydrateLoginForm() {
    const form = document.getElementById('login-form');
    if (!form) {
        return;
    }

    prepareSubmitButton(form);

    const emailInput = document.getElementById('login-email');
    const registeredEmail = sessionStorage.getItem('pending_login_email');
    const registeredFlag = new URLSearchParams(window.location.search).get('registered');

    if (registeredEmail && emailInput && !emailInput.value) {
        emailInput.value = registeredEmail;
    }

    if (registeredFlag) {
        setMessage('login-form', 'Account created. Sign in to continue.', 'success');
        sessionStorage.removeItem('pending_login_email');
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        setMessage('login-form', '');
        const formData = new FormData(form);
        setFormBusy(form, true);

        try {
            await handleLogin(formData);
        } catch (error) {
            setMessage('login-form', error instanceof Error ? error.message : 'Unable to sign in.');
        } finally {
            setFormBusy(form, false);
        }
    });
}

function hydrateRegisterForm() {
    const form = document.getElementById('register-form');
    if (!form) {
        return;
    }

    prepareSubmitButton(form);

    const { emailInput, passwordInput, confirmPasswordInput } = getRegisterPasswordElements();

    if (emailInput) {
        const syncEmailValidity = () => {
            updateEmailValidityState();
        };

        emailInput.addEventListener('input', syncEmailValidity);
        emailInput.addEventListener('blur', syncEmailValidity);
        updateEmailValidityState();
    }

    if (passwordInput && confirmPasswordInput) {
        const syncPasswordMatch = () => {
            updatePasswordMatchState();
        };

        passwordInput.addEventListener('input', syncPasswordMatch);
        confirmPasswordInput.addEventListener('input', syncPasswordMatch);
        updatePasswordMatchState();
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        setMessage('register-form', '');
        const formData = new FormData(form);

        const isEmailValid = updateEmailValidityState();

        if (!isEmailValid) {
            setMessage('register-form', 'Email must be a valid email address.');
            emailInput?.focus();
            return;
        }

        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }

        if (!updatePasswordMatchState()) {
            setMessage('register-form', 'Passwords do not match.');
            const { confirmPasswordInput } = getRegisterPasswordElements();
            confirmPasswordInput?.focus();
            return;
        }

        setFormBusy(form, true);

        try {
            await handleRegister(formData);
        } catch (error) {
            setMessage('register-form', error instanceof Error ? error.message : error);
        } finally {
            setFormBusy(form, false);
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    hydrateLoginForm();
    hydrateRegisterForm();
});
