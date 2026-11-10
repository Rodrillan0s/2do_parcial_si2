# Pruebas de Casos de Uso — Iteración 1

### Prueba de caso de uso CU1: Registrar cliente

| Caso de uso 1 | Registrar cliente |
| :--- | :--- |
| **Descripción** | Este caso de uso permite que un nuevo cliente pueda crear su cuenta personal en el sistema ingresando sus datos principales para poder acceder a la tienda y realizar compras. |
| **Precondiciones** | a) El usuario debe tener acceso a la página principal.<br>b) El formulario de registro debe estar habilitado.<br>c) Debe existir conexión activa con la base de datos. |

| Paso | Acción | Resultado esperado | Estado (Satisfactorio/Fallido) |
| :---: | :--- | :--- | :---: |
| 1 | Acceder a la opción de registro desde la pantalla principal. | Se muestra el formulario con los campos de nombre, apellido, correo, teléfono y contraseña. | Satisfactorio |
| 2 | Ingresar los datos solicitados y confirmar. | Se valida que el correo no esté repetido; la cuenta se crea correctamente. | Satisfactorio |
| 3 | Confirmar el registro exitoso. | Se muestra un mensaje de bienvenida y se redirige a la pantalla de inicio de sesión. | Satisfactorio |
| 4 | Intentar registrar un cliente con un correo ya existente. | Se muestra un mensaje de advertencia indicando que el correo ya está en uso. | Satisfactorio |

---

### Prueba de caso de uso CU2: Iniciar sesión

| Caso de uso 2 | Iniciar sesión |
| :--- | :--- |
| **Descripción** | Este caso de uso permite que los usuarios registrados ingresen al sistema mediante su usuario y contraseña para acceder a las opciones según su rol asignado. |
| **Precondiciones** | a) El usuario debe contar con una cuenta activa en el sistema.<br>b) El módulo de inicio de sesión debe estar habilitado.<br>c) Debe existir conexión activa con la base de datos. |

| Paso | Acción | Resultado esperado | Estado (Satisfactorio/Fallido) |
| :---: | :--- | :--- | :---: |
| 1 | Acceder a la pantalla de inicio de sesión. | Se muestra la vista con los campos de usuario y contraseña. | Satisfactorio |
| 2 | Ingresar usuario y contraseña correctos. | El sistema valida los datos y permite el ingreso a la plataforma. | Satisfactorio |
| 3 | Redirección de pantalla. | El usuario es dirigido al menú principal correspondiente a su rol. | Satisfactorio |
| 4 | Ingresar una contraseña incorrecta. | Se muestra una alerta indicando que los datos ingresados no son correctos. | Satisfactorio |

---

### Prueba de caso de uso CU3: Gestionar perfil

| Caso de uso 3 | Gestionar perfil |
| :--- | :--- |
| **Descripción** | Este caso de uso permite que el usuario pueda consultar su información personal, modificar sus datos de contacto y mantener su cuenta actualizada. |
| **Precondiciones** | a) El usuario debe tener la sesión iniciada.<br>b) El módulo de perfil debe estar habilitado.<br>c) Debe existir conexión activa con la base de datos. |

| Paso | Acción | Resultado esperado | Estado (Satisfactorio/Fallido) |
| :---: | :--- | :--- | :---: |
| 1 | Acceder a la sección "Mi Perfil" desde el menú de usuario. | Se muestran los datos del usuario registrados actualmente. | Satisfactorio |
| 2 | Modificar el número de teléfono o datos de contacto. | Los campos permiten la edición y se valida que tengan el formato correcto. | Satisfactorio |
| 3 | Guardar los cambios realizados. | Se actualiza la información y se muestra un mensaje de confirmación. | Satisfactorio |
| 4 | Actualizar la vista. | La pantalla refleja de inmediato los datos modificados. | Satisfactorio |

---

### Prueba de caso de uso CU4: Consultar catálogo de prendas

| Caso de uso 4 | Consultar catálogo de prendas |
| :--- | :--- |
| **Descripción** | Este caso de uso permite explorar las prendas de vestir disponibles, filtrar por categorías o precios y consultar el detalle de tallas, colores y disponibilidad. |
| **Precondiciones** | a) Deben existir productos registrados en el sistema.<br>b) El catálogo público debe estar disponible.<br>c) Debe existir conexión activa con la base de datos. |

| Paso | Acción | Resultado esperado | Estado (Satisfactorio/Fallido) |
| :---: | :--- | :--- | :---: |
| 1 | Ingresar al catálogo desde la pantalla principal. | Se muestra la lista de prendas con su fotografía, nombre y precio. | Satisfactorio |
| 2 | Seleccionar una categoría en el filtro de búsqueda. | La lista se actualiza mostrando únicamente las prendas de la categoría seleccionada. | Satisfactorio |
| 3 | Seleccionar una prenda para ver su detalle. | Se despliega una vista con la descripción, fotos, tallas y colores disponibles. | Satisfactorio |
| 4 | Elegir una talla y color determinados. | El sistema muestra la cantidad disponible para esa combinación. | Satisfactorio |

---

### Prueba de caso de uso CU14: Gestionar usuarios y roles

| Caso de uso 14 | Gestión de usuarios y roles |
| :--- | :--- |
| **Descripción** | Este caso de uso permite que el administrador consulte los usuarios registrados, cree nuevas cuentas del personal, asigne o modifique roles y habilite o deshabilite accesos. |
| **Precondiciones** | a) El usuario debe iniciar sesión como Administrador.<br>b) El módulo "Usuarios y Roles" debe estar habilitado.<br>c) Debe existir conexión activa con la base de datos. |

| Paso | Acción | Resultado esperado | Estado (Satisfactorio/Fallido) |
| :---: | :--- | :--- | :---: |
| 1 | Acceder al módulo "Usuarios" desde el menú principal. | Se muestra la lista de usuarios registrados con su nombre, correo, rol y estado. | Satisfactorio |
| 2 | Crear un nuevo usuario del sistema. | Se valida que el usuario y correo no estén repetidos; se guarda correctamente. | Satisfactorio |
| 3 | Editar el rol de un usuario existente. | Se actualiza el rol asignado y se muestra un mensaje de confirmación. | Satisfactorio |
| 4 | Desactivar la cuenta de un usuario. | El estado cambia a inactivo y el usuario ya no puede ingresar al sistema. | Satisfactorio |
| 5 | Actualizar lista visible. | La tabla refleja inmediatamente los cambios realizados. | Satisfactorio |

---

### Prueba de caso de uso CU15: Gestionar cadena de tiendas

| Caso de uso 15 | Gestión de cadena de tiendas |
| :--- | :--- |
| **Descripción** | Este caso de uso permite registrar las empresas o tiendas pertenecientes a la plataforma, modificar su información comercial y consultar su estado operativo. |
| **Precondiciones** | a) El usuario debe iniciar sesión como Administrador General.<br>b) El módulo "Tiendas / Empresas" debe estar habilitado.<br>c) Debe existir conexión activa con la base de datos. |

| Paso | Acción | Resultado esperado | Estado (Satisfactorio/Fallido) |
| :---: | :--- | :--- | :---: |
| 1 | Acceder al módulo "Tiendas" desde el menú principal. | Se muestra la lista de empresas registradas con su nombre, NIT y estado. | Satisfactorio |
| 2 | Registrar una nueva tienda ingresando nombre y NIT. | Se valida que el NIT no esté duplicado; la tienda se guarda correctamente. | Satisfactorio |
| 3 | Modificar los datos de una tienda existente. | Se actualiza la información y se muestra un mensaje de confirmación. | Satisfactorio |
| 4 | Ver detalles de una tienda. | Se despliega una vista con la información completa de la empresa. | Satisfactorio |
| 5 | Cambiar estado a inactivo. | La tienda cambia de estado y se actualiza la lista visible. | Satisfactorio |

---

### Prueba de caso de uso CU16: Gestionar sucursales y ciudades

| Caso de uso 16 | Gestión de sucursales y ciudades |
| :--- | :--- |
| **Descripción** | Este caso de uso permite registrar los puntos de venta físicos de cada tienda, asignarlos a una ciudad, registrar su dirección y administrar su estado de atención. |
| **Precondiciones** | a) El usuario debe tener permisos de administración.<br>b) Deben existir ciudades registradas en el sistema.<br>c) Debe existir conexión activa con la base de datos. |

| Paso | Acción | Resultado esperado | Estado (Satisfactorio/Fallido) |
| :---: | :--- | :--- | :---: |
| 1 | Acceder al módulo "Sucursales" desde el menú principal. | Se muestra la lista de sucursales con su nombre, código, ciudad y estado. | Satisfactorio |
| 2 | Registrar una nueva sucursal con su ciudad y dirección. | Se valida que el código no esté repetido; la sucursal se guarda correctamente. | Satisfactorio |
| 3 | Modificar la dirección o teléfono de una sucursal. | Se actualizan los datos y se muestra confirmación en pantalla. | Satisfactorio |
| 4 | Ver detalles de una sucursal. | Se despliega la información completa del punto de venta. | Satisfactorio |
| 5 | Desactivar una sucursal. | La sucursal cambia a estado inactivo y no aparece para entregas al cliente. | Satisfactorio |

---

### Prueba de caso de uso CU17: Gestionar productos

| Caso de uso 17 | Gestión de productos |
| :--- | :--- |
| **Descripción** | Este caso de uso permite registrar prendas de vestir en el catálogo, modificar sus precios, actualizar descripciones y administrar su visibilidad para la venta. |
| **Precondiciones** | a) El usuario debe tener rol de Administrador o Encargado.<br>b) Debe existir al menos una categoría creada.<br>c) Debe existir conexión activa con la base de datos. |

| Paso | Acción | Resultado esperado | Estado (Satisfactorio/Fallido) |
| :---: | :--- | :--- | :---: |
| 1 | Acceder al módulo "Productos" desde el menú principal. | Se muestra la lista de productos registrados con su foto, código, nombre y precio. | Satisfactorio |
| 2 | Crear un nuevo producto con su nombre, categoría y precio. | Se valida que el precio sea mayor a cero; el producto se guarda correctamente. | Satisfactorio |
| 3 | Modificar el precio de una prenda existente. | Se actualiza el precio y se muestra confirmación en pantalla. | Satisfactorio |
| 4 | Ver detalles de un producto. | Se despliega la vista con toda la información completa de la prenda. | Satisfactorio |
| 5 | Desactivar un producto. | La prenda deja de mostrarse en la tienda pública de clientes. | Satisfactorio |

---

### Prueba de caso de uso CU18: Gestionar categorías

| Caso de uso 18 | Gestión de categorías |
| :--- | :--- |
| **Descripción** | Este caso de uso permite crear y administrar las categorías de ropa (ejemplo: Poleras, Pantalones, Calzados) para organizar los productos en el catálogo. |
| **Precondiciones** | a) El usuario debe tener permisos de administración de catálogo.<br>b) El módulo "Categorías" debe estar habilitado.<br>c) Debe existir conexión activa con la base de datos. |

| Paso | Acción | Resultado esperado | Estado (Satisfactorio/Fallido) |
| :---: | :--- | :--- | :---: |
| 1 | Acceder al módulo "Categorías" desde el menú principal. | Se muestra la lista de categorías existentes con su nombre y descripción. | Satisfactorio |
| 2 | Crear una nueva categoría ingresando su nombre. | Se valida que el nombre no esté repetido; se guarda correctamente. | Satisfactorio |
| 3 | Modificar el nombre o descripción de una categoría. | Se actualizan los datos del registro y se muestra mensaje de confirmación. | Satisfactorio |
| 4 | Ver detalles de una categoría. | Se muestra la información completa y la lista de productos vinculados. | Satisfactorio |
| 5 | Actualizar lista visible. | La nueva categoría aparece disponible en la lista y en los formularios. | Satisfactorio |

---

### Prueba de caso de uso CU19: Gestionar tallas y colores

| Caso de uso 19 | Gestión de tallas y colores |
| :--- | :--- |
| **Descripción** | Este caso de uso permite configurar las combinaciones de tallas y colores para cada prenda y registrar las cantidades de inventario disponibles. |
| **Precondiciones** | a) La prenda debe estar registrada previamente en el catálogo.<br>b) El módulo de variantes debe estar habilitado.<br>c) Debe existir conexión activa con la base de datos. |

| Paso | Acción | Resultado esperado | Estado (Satisfactorio/Fallido) |
| :---: | :--- | :--- | :---: |
| 1 | Seleccionar una prenda y entrar a "Variantes de Producto". | Se muestra la lista de combinaciones de tallas y colores de esa prenda. | Satisfactorio |
| 2 | Agregar una combinación seleccionando talla y color. | Se valida que la combinación no exista previamente para la prenda. | Satisfactorio |
| 3 | Ingresar la cantidad de stock inicial y confirmar. | La variante se guarda correctamente con la cantidad indicada. | Satisfactorio |
| 4 | Modificar la cantidad disponible de una combinación. | Se actualiza la cantidad en inventario y se muestra confirmación. | Satisfactorio |
| 5 | Actualizar lista visible. | La tabla muestra de inmediato el nuevo stock de cada talla y color. | Satisfactorio |
