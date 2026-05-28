import os
from datetime import datetime, timezone
from app.database import engine, Base, SessionLocal
from app.models import Expert, Ticket, AgentActionLog, User
from app.services.classifier import classify_ticket
from app.services.router import route_ticket_to_expert
from app.services.sla import calculate_sla_deadline
from app.services.auth import hash_password

def seed_database():
    print("⏳ Seeding database and running initial multi-agent pipeline...")
    
    # 1. Recreate tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 2. Seed Admin User
        admin_pwd = hash_password("admin123")
        admin_user = User(
            email="admin@company.com",
            hashed_password=admin_pwd,
            role="Admin",
            expert_id=None
        )
        db.add(admin_user)
        print("👤 Admin user registered: admin@company.com / admin123")

        # 3. Seed Experts and their matching User logins
        experts_data = [
            # Network Experts
            {"name": "Priya Sharma", "category": "Network", "skills": "VPN, Firewall, Network Security, Cisco"},
            {"name": "Rajesh Patel", "category": "Network", "skills": "Wi-Fi, DNS, Network Infrastructure, Routers"},
            # Software Experts
            {"name": "Anjali Mehta", "category": "Software", "skills": "Windows, Applications, Software Licensing, MS Office"},
            {"name": "Arjun Reddy", "category": "Software", "skills": "macOS, Software Installation, Debugging, Linux"},
            # Hardware Experts
            {"name": "Kavya Nair", "category": "Hardware", "skills": "Laptops, Desktops, Peripherals, Hardware Diagnostics"},
            {"name": "Vikram Singh", "category": "Hardware", "skills": "Printers, Monitors, Hardware Repair, Components"},
            # Cloud Experts
            {"name": "Neha Gupta", "category": "Cloud", "skills": "AWS, Azure, Cloud Storage, Migration"},
            {"name": "Karthik Iyer", "category": "Cloud", "skills": "GCP, Cloud Security, DevOps, Kubernetes"},
            # General Support
            {"name": "Sneha Desai", "category": "General", "skills": "General Support, User Training, Documentation"}
        ]
        
        expert_password = hash_password("expert123")
        for exp in experts_data:
            # 3a. Save expert profile
            expert = Expert(
                name=exp["name"],
                category=exp["category"],
                skills=exp["skills"],
                is_active=True
            )
            db.add(expert)
            db.flush() # Yields the expert.id

            # 3b. Create matching expert user account
            email = f"{expert.name.lower().replace(' ', '.')}@company.com"
            user = User(
                email=email,
                hashed_password=expert_password,
                role="Expert",
                expert_id=expert.id
            )
            db.add(user)
            
        db.flush()
        print(f"👥 Registered {len(experts_data)} experts and created their corresponding user logins (Password: 'expert123').")

        # 4. Create and route sample tickets
        sample_tickets = [
            {
                "title": "VPN Connection Issues",
                "description": "Cannot connect to corporate VPN. Urgent - need access for client meeting ASAP!"
            },
            {
                "title": "Software License Expired",
                "description": "My Microsoft Office license expired. Need help to renew it for drafting reports."
            },
            {
                "title": "Laptop Screen Broken",
                "description": "Laptop screen has a vertical pink line after dropping it. Need diagnostic or screen replacement."
            }
        ]

        print("\n🚀 Processing sample tickets through the agent pipeline...")
        for t_data in sample_tickets:
            now = datetime.now(timezone.utc)
            ticket = Ticket(
                title=t_data["title"],
                description=t_data["description"],
                status="New",
                created_at=now,
                is_sla_breached=False
            )
            db.add(ticket)
            db.flush() # Assigns ID

            # Classification
            classification = classify_ticket(t_data["title"], t_data["description"])
            ticket.category = classification["category"]
            ticket.priority = classification["priority"]
            ticket.sla_deadline = calculate_sla_deadline(now, classification["priority"])

            # Classification logs
            db.add(AgentActionLog(
                ticket_id=ticket.id,
                agent="ClassificationAgent",
                action="classify",
                result=f"Category: {classification['category']} | Source: {classification['category_source']}"
            ))
            db.add(AgentActionLog(
                ticket_id=ticket.id,
                agent="PrioritizationAgent",
                action="prioritize",
                result=f"Priority: {classification['priority']} | Source: {classification['priority_source']}"
            ))

            # Routing
            route_ticket_to_expert(db, ticket)
            print(f"  🎫 Ticket #{ticket.id} Classified as {ticket.category} ({ticket.priority} priority) -> Routed to {ticket.assignee}")
        
        db.commit()
        print("\n🎉 Database successfully initialized with seeded user accounts and sample routed tickets.")
    except Exception as e:
        db.rollback()
        print(f"❌ Error during database seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
