
---

📄 **`docs/workflow.md`**

# 🧪 Git Workflow

Este documento define el flujo de trabajo estándar basado en tres ramas principales: `development`, `test` y `production`.

---

## 📌 Estructura de ramas

- **`development`**: rama base para integración de nuevas funcionalidades.
- **`test`**: rama para pruebas manuales o automáticas (QA).
- **`production`**: rama estable para despliegue en producción.

---

## 🔁 Flujo de trabajo general

```
feature/* → test → development → production
````

---

## 🚧 Flujo de desarrollo

1. Crear una rama por funcionalidad:

   ```bash
   git checkout development
   git checkout -b feature/nueva-funcionalidad
   ```

2. Hacer commits y push:

   ```bash
   git commit -m "feat: agrega nueva funcionalidad"
   git push origin feature/nueva-funcionalidad
   ```

3. Crear Pull Request hacia `test`.

4. QA revisa la funcionalidad en `test`.

5. Si se aprueba, se hace merge a `development`.

6. Al preparar el release:

   ```bash
   git checkout production
   git merge development
   git push origin production
   ```

---

## 🛡️ Buenas prácticas

* Usar prefijos en ramas: `feature/`, `bugfix/`, `hotfix/`, etc.
* Hacer commits descriptivos y consistentes.
* Configurar ramas protegidas:

  * `production` y `development` deben requerir Pull Requests.

---

## 📌 Ejemplo de nombres de ramas

* `feature/login-form`
* `bugfix/fix-navbar`
* `hotfix/crash-on-load`

---
