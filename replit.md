# AGRI.vendasMz - Agricultural Marketplace Platform

## Overview

AGRI.vendasMz is a comprehensive agricultural marketplace platform designed specifically for Mozambique. It connects farmers, buyers, and agricultural stakeholders through a web-based marketplace with integrated consultancy services. The platform enables users to buy and sell agricultural products, access farming guidance, receive expert agricultural advice, and purchase agricultural equipment.

The application is built as a Flask-based monolithic web application with SQLite for data persistence, featuring user authentication, product listings, premium membership tiers, equipment store, and an administrative panel for platform management.

## Recent Changes (November 2025)

### 1. Enhanced Agricultural Consultancy System
- Expanded crop database from 4 to 50+ crops across 8 categories:
  - Cereais (milho, arroz, trigo, sorgo, aveia, cevada)
  - Hortícolas (tomate, alface, cenoura, couve, cebola, pimento, repolho, pepino, abóbora)
  - Frutícolas (manga, banana, citrinos, maçã, uva, abacate, papaia, ananás)
  - Tubérculos (mandioca, batata, batata-doce, inhame)
  - Leguminosas (feijão, soja, grão-de-bico, amendoim, ervilha, feijão-nhemba)
  - Oleaginosas (girassol, gergelim, coco)
  - Medicinais (aloe-vera, manjericão, hortelã, moringa)
  - Regionais (mapira, mexoeira, mucuna, cajueiro, algodão)
- Added dual-unit area input (hectares and square meters) with automatic conversion
- Comprehensive crop data including: soil requirements, temperature, altitude, planting seasons, common pests/diseases, planting density

### 2. Equipment Store System
- New beautiful store template at `/loja` route
- Equipment database table with full CRUD operations
- Category filtering (Tratores, Irrigação, Ferramentas, Pulverizadores, Colheita, Armazenamento)
- Price filtering
- WhatsApp contact integration for inquiries
- Modern responsive design with hover animations

### 3. Super Admin Equipment Management
- New "Equipamentos" tab in admin panel (super admin only)
- Add/Edit/Remove equipment with image upload
- Equipment status tracking (disponível, reservado, vendido)
- Stock management
- Location and contact information

### 4. UI/UX Improvements
- Green gradient color scheme (#1B5E20, #2E7D32, #4CAF50) for agricultural theme
- Card-based layouts with hover animations and shadows
- Updated navigation to include equipment store link
- Responsive design improvements

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Template Engine**: Jinja2 templates with server-side rendering
- **UI Framework**: Bootstrap 5.3.0 for responsive design
- **Icons**: Font Awesome 6.0.0 for iconography
- **Typography**: Google Fonts (Poppins family)
- **Styling Approach**: Custom CSS with CSS variables for theming, combined with Bootstrap utilities
- **Design Pattern**: Traditional multi-page application (MPA) with form-based navigation

**Rationale**: Server-side rendering provides simplicity, better SEO, and reduces JavaScript dependencies. Bootstrap ensures mobile-first responsive design without custom CSS frameworks.

### Backend Architecture
- **Framework**: Flask 2.3.2 (Python micro-framework)
- **Architecture Pattern**: Monolithic application with route-based controllers
- **Session Management**: Flask sessions with server-side secret key
- **Authentication**: Password hashing with Werkzeug's security utilities
- **File Uploads**: Werkzeug secure filename handling with size limits (16MB max)
- **Authorization**: Custom decorator-based role checking (admin, premium, vendor, buyer)

**Rationale**: Flask provides lightweight, flexible routing ideal for small-to-medium applications. Monolithic architecture simplifies deployment on platforms like Replit.

### Data Storage
- **Primary Database**: SQLite 3 (file-based relational database)
- **Schema Design**: Normalized tables with foreign key relationships
- **Key Tables**:
  - `usuarios` (users) - User accounts with role-based types
  - `produtos` (products) - Product listings linked to vendors
  - `equipamentos` (equipment) - Agricultural equipment for sale
  - `administradores` - Admin user tracking
  - `configuracoes_sistema` - System configuration
  - `configuracoes_admin` - Admin access configuration

**Rationale**: SQLite requires no separate database server, making it ideal for development and small-scale deployments. Easy to migrate to PostgreSQL later if needed.

**Limitations**: SQLite is not suitable for high-concurrency production workloads. Consider migrating to PostgreSQL for production scale.

### Authentication & Authorization
- **Authentication Method**: Email/phone + password with hashed storage
- **Password Hashing**: Werkzeug's `generate_password_hash` and `check_password_hash`
- **Session Storage**: Flask server-side sessions
- **User Roles**: 
  - `comprador` (buyer)
  - `vendedor` (seller/vendor)
  - `admin`
  - `superadmin`
  - Premium status tracked separately via `premium` flag and expiration date
- **Super Admin Access Code**: AGRI2024ADMIN (configurable in admin panel)
- **Default Admin**: Phone 878312890, Password: 12345,Ibrahim

**Rationale**: Password hashing prevents credential theft. Role-based access control enables tiered feature access. Session-based auth simplifies implementation over token-based approaches.

### File Upload System
- **Upload Directory**: `static/uploads/`
- **Security**: Werkzeug `secure_filename` prevents path traversal attacks
- **Size Limit**: 16MB maximum file size
- **Use Case**: Product photos, equipment images, and potentially user avatars

**Rationale**: Storing uploads in the static directory allows direct serving via Flask without CDN complexity. Size limits prevent abuse.

### Premium Membership System
- **Premium Tracking**: Boolean flag + expiration date in user table
- **Payment Integration**: Manual payment verification (M-Pesa reference number: 847214191)
- **Pricing**: 199 MT/month
- **Features**: Unlimited listings, advanced filters, detailed crop information, SMS alerts, priority support

**Rationale**: Manual payment processing avoids complex payment gateway integrations initially. Can be automated later with M-Pesa API integration.

### Administrative Panel
- **Access Control**: Two-tier admin system (admin and superadmin)
- **Authentication**: Separate admin code-based access system
- **Features**: 
  - User management (activate/deactivate premium, ban users)
  - Product moderation
  - Analytics/reporting
  - Equipment management (super admin only)
  - Admin nomination (super admin only)
  - Security configuration (super admin only)
- **Recovery System**: Admin code recovery via email or phone

**Rationale**: Separate admin authentication adds security layer. Code-based access simpler than complex RBAC systems for small teams.

### Application Entry Points
- **Development**: `main.py` runs Flask directly on port 5000
- **Production**: `start.py` launches Gunicorn WSGI server on port 10000
- **Database Initialization**: `init_db()` creates tables on startup

**Rationale**: Gunicorn provides production-grade WSGI serving with better performance than Flask's development server.

## Key Routes

### Public Routes
- `/` - Homepage
- `/produtos` - Product listings
- `/loja` - Equipment store
- `/login` - User login
- `/cadastro` - User registration

### Authenticated Routes
- `/dashboard` - User dashboard
- `/consultoria` - Agricultural consultancy (with crop calculator)
- `/calcular_plantio` - API endpoint for crop calculations
- `/publicar` - Publish new product (vendors only)
- `/premium` - Premium subscription page

### Admin Routes
- `/admin` - Admin panel
- `/admin/acesso` - Super admin access code entry
- `/admin/equipamentos/novo` - Add new equipment (super admin)
- `/admin/equipamentos/<id>/editar` - Edit equipment (super admin)
- `/admin/equipamentos/<id>/remover` - Remove equipment (super admin)

## External Dependencies

### Python Packages
- **Flask 2.3.2**: Web framework (core dependency)
- **Werkzeug 3.0.1**: WSGI utilities, security helpers (comes with Flask)
- **Gunicorn 21.2.0**: Production WSGI HTTP server
- **PyJWT 2.8.0**: JWT token encoding/decoding

### Frontend Libraries (CDN-based)
- **Bootstrap 5.3.0**: UI component framework and grid system
- **Font Awesome 6.0.0**: Icon library
- **Google Fonts**: Poppins font family

**Rationale**: CDN delivery reduces bundle size and leverages browser caching. No build process required.

### Database
- **SQLite3**: Bundled with Python, no external installation required

### Third-Party Service Integrations
- **M-Pesa Mobile Money**: Payment processing (manual integration, no API)
  - Reference number: 847214191
  - Used for premium subscription payments (199 MT/month)
- **WhatsApp**: Contact integration for equipment inquiries

**Future Considerations**: 
- Automated M-Pesa API integration for payment verification
- SMS gateway integration for alerts (mentioned in premium features)
- Email service for notifications and admin code recovery
- Migration to PostgreSQL for production scalability

### Deployment Platform
- **Target Platform**: Replit or similar cloud platforms
- **Port Configuration**: Configured for port 5000 (development) / 10000 (production)
- **Static File Serving**: Flask serves static files directly

**Note**: The application currently uses SQLite but may require PostgreSQL integration for production deployment on platforms like Replit with persistent database requirements.
