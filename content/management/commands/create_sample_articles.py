"""
Django management command to create sample articles with images and formatting.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from content.models import Article, Category, Tag
from core.utils import StringHelper
from datetime import timedelta
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Create 10 sample articles with images and rich formatting for the Somali Report platform'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing articles before creating new ones',
        )
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of articles to create (default: 10)',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        count = options['count']
        
        if options['clear']:
            self.stdout.write('Clearing existing articles...')
            Article.objects.all().delete()
            self.stdout.write(
                self.style.SUCCESS('Successfully cleared existing articles')
            )

        # Get or create required data
        categories = Category.objects.all()
        tags = Tag.objects.all()
        users = User.objects.all()
        
        if not categories.exists():
            self.stdout.write(
                self.style.WARNING('No categories found. Run create_sample_data first.')
            )
            return
            
        if not users.exists():
            self.stdout.write(
                self.style.WARNING('No users found. Create a user first.')
            )
            return

        with transaction.atomic():
            articles = self.create_articles(count, categories, tags, users)
            self.stdout.write(
                self.style.SUCCESS(f'\nSuccessfully created {len(articles)} articles')
            )

        self.stdout.write(
            self.style.SUCCESS('\nSample articles creation completed successfully!')
        )

    def create_articles(self, count, categories, tags, users):
        """Create sample articles with rich formatting."""
        article_templates = [
            {
                'title': 'Somali Government Announces New Economic Reforms',
                'excerpt': 'The Somali government has unveiled comprehensive economic reforms aimed at boosting growth and attracting foreign investment.',
                'content': '''<h2>Major Economic Policy Changes</h2>
<p>The Ministry of Finance has announced a series of <strong>groundbreaking economic reforms</strong> that will reshape Somalia's financial landscape. These reforms come after months of consultation with international partners and local business leaders.</p>

<h3>Key Reforms Include:</h3>
<ul>
    <li>Simplified tax structure for small businesses</li>
    <li>Investment incentives for technology companies</li>
    <li>Improved banking regulations</li>
    <li>Enhanced trade facilitation measures</li>
</ul>

<p>The reforms are expected to <em>stimulate economic growth</em> and create thousands of new jobs across various sectors.</p>

<h3>Impact on Local Businesses</h3>
<p>Local business owners have expressed optimism about the new policies. "This is exactly what we needed to compete on a global scale," said one entrepreneur.</p>

<p>The government plans to implement these changes gradually over the next 12 months, with full implementation expected by next year.</p>''',
                'status': 'published',
                'priority': 'high',
                'is_featured': True,
                'is_breaking': False,
            },
            {
                'title': 'Breaking: Major Infrastructure Project Launched in Mogadishu',
                'excerpt': 'A new transportation hub project begins construction, expected to transform the city\'s connectivity.',
                'content': '''<h2>Infrastructure Milestone</h2>
<p>The city of Mogadishu has embarked on its <strong>largest infrastructure project</strong> in decades. The new transportation hub will connect major districts and improve mobility for millions of residents.</p>

<h3>Project Details</h3>
<p>The project includes:</p>
<ol>
    <li>Modern bus terminals with smart ticketing systems</li>
    <li>Integrated railway connections</li>
    <li>Bicycle lanes and pedestrian walkways</li>
    <li>Electric vehicle charging stations</li>
</ol>

<p>Construction is expected to be completed in phases, with the first phase opening to the public within 18 months.</p>

<h3>Economic Benefits</h3>
<p>This project will create <em>over 5,000 jobs</em> during construction and another 1,000 permanent positions once operational.</p>''',
                'status': 'published',
                'priority': 'urgent',
                'is_featured': True,
                'is_breaking': True,
            },
            {
                'title': 'Technology Sector Shows Rapid Growth in Somalia',
                'excerpt': 'Startups and tech companies are flourishing, with record investments and innovative solutions emerging.',
                'content': '''<h2>Tech Revolution in Somalia</h2>
<p>Somalia's technology sector is experiencing <strong>unprecedented growth</strong>, with startups raising millions in funding and creating innovative solutions for local and global markets.</p>

<h3>Success Stories</h3>
<p>Several tech companies have achieved remarkable success:</p>
<ul>
    <li>Mobile payment platforms reaching millions of users</li>
    <li>E-commerce platforms transforming retail</li>
    <li>Education technology improving access to learning</li>
    <li>Healthcare tech solutions enhancing medical services</li>
</ul>

<p>Industry experts predict this trend will continue as more investors recognize the potential of Somalia's tech ecosystem.</p>

<h3>Future Outlook</h3>
<p>The government's support for innovation and entrepreneurship is creating a fertile ground for <em>future tech giants</em> to emerge.</p>''',
                'status': 'published',
                'priority': 'normal',
                'is_featured': False,
                'is_breaking': False,
            },
            {
                'title': 'Education Reform Brings Hope to Youth',
                'excerpt': 'New educational initiatives are providing opportunities for thousands of young Somalis.',
                'content': '''<h2>Transforming Education</h2>
<p>Comprehensive education reforms are bringing <strong>new opportunities</strong> to Somali youth across the country. These initiatives focus on improving access, quality, and relevance of education.</p>

<h3>Key Initiatives</h3>
<p>The reform program includes:</p>
<ol>
    <li>Modernizing curriculum to meet global standards</li>
    <li>Training and supporting teachers</li>
    <li>Building new schools in underserved areas</li>
    <li>Introducing technology in classrooms</li>
</ol>

<p>Students and parents have welcomed these changes, seeing them as a pathway to <em>better futures</em>.</p>

<h3>Impact on Communities</h3>
<p>Early results show increased enrollment rates and improved learning outcomes in pilot programs.</p>''',
                'status': 'published',
                'priority': 'high',
                'is_featured': True,
                'is_breaking': False,
            },
            {
                'title': 'Healthcare Improvements Benefit Rural Communities',
                'excerpt': 'Mobile health clinics and telemedicine services are reaching remote areas for the first time.',
                'content': '''<h2>Healthcare Access Expanded</h2>
<p>Innovative healthcare programs are bringing <strong>medical services</strong> to communities that previously had limited access. Mobile clinics and telemedicine are making a significant difference.</p>

<h3>Program Highlights</h3>
<ul>
    <li>Mobile health units visiting remote villages</li>
    <li>Telemedicine consultations with specialists</li>
    <li>Vaccination campaigns reaching thousands</li>
    <li>Maternal and child health programs</li>
</ul>

<p>These initiatives are saving lives and improving quality of life for <em>thousands of families</em> across Somalia.</p>

<h3>Community Response</h3>
<p>Local communities have expressed gratitude for these life-changing services, with many calling for expanded coverage.</p>''',
                'status': 'published',
                'priority': 'normal',
                'is_featured': False,
                'is_breaking': False,
            },
            {
                'title': 'Cultural Festival Celebrates Somali Heritage',
                'excerpt': 'Annual festival showcases traditional music, dance, and arts, attracting visitors from around the world.',
                'content': '''<h2>Celebrating Somali Culture</h2>
<p>The annual Somali Cultural Festival has returned, showcasing the <strong>rich heritage</strong> and traditions of the Somali people. This year's event features performances, exhibitions, and workshops.</p>

<h3>Festival Features</h3>
<p>Attendees can enjoy:</p>
<ol>
    <li>Traditional music and dance performances</li>
    <li>Art exhibitions by local artists</li>
    <li>Culinary experiences with authentic Somali cuisine</li>
    <li>Handicraft markets and workshops</li>
</ol>

<p>The festival provides a platform for <em>cultural preservation</em> and exchange, bringing together Somalis from all backgrounds.</p>

<h3>International Recognition</h3>
<p>This year's festival has attracted international attention, with visitors from across Africa and beyond.</p>''',
                'status': 'published',
                'priority': 'normal',
                'is_featured': False,
                'is_breaking': False,
            },
            {
                'title': 'Sports Teams Achieve International Success',
                'excerpt': 'Somali athletes and teams are making their mark on the global stage with impressive performances.',
                'content': '''<h2>Athletic Excellence</h2>
<p>Somali sports teams have achieved <strong>remarkable success</strong> in international competitions, bringing pride to the nation and inspiring young athletes.</p>

<h3>Recent Achievements</h3>
<ul>
    <li>National football team advances in continental tournament</li>
    <li>Track and field athletes set new records</li>
    <li>Youth teams win regional championships</li>
    <li>Individual athletes qualify for major international events</li>
</ul>

<p>These accomplishments are the result of <em>dedicated training</em> and improved support for athletes.</p>

<h3>Inspiring the Next Generation</h3>
<p>Young people across Somalia are being inspired to pursue sports, seeing the success of their heroes.</p>''',
                'status': 'published',
                'priority': 'normal',
                'is_featured': False,
                'is_breaking': False,
            },
            {
                'title': 'Agricultural Innovation Boosts Food Security',
                'excerpt': 'New farming techniques and technologies are increasing crop yields and improving food security.',
                'content': '''<h2>Farming for the Future</h2>
<p>Agricultural innovations are transforming farming practices in Somalia, leading to <strong>increased productivity</strong> and better food security for communities.</p>

<h3>Innovative Approaches</h3>
<p>Farmers are adopting:</p>
<ol>
    <li>Drip irrigation systems for water conservation</li>
    <li>Improved seed varieties adapted to local conditions</li>
    <li>Organic farming methods for sustainable agriculture</li>
    <li>Mobile apps for market information and weather</li>
</ol>

<p>These innovations are helping farmers achieve <em>higher yields</em> while protecting the environment.</p>

<h3>Community Impact</h3>
<p>Rural communities are benefiting from improved food availability and increased incomes from agriculture.</p>''',
                'status': 'published',
                'priority': 'high',
                'is_featured': True,
                'is_breaking': False,
            },
            {
                'title': 'Women Entrepreneurs Drive Economic Growth',
                'excerpt': 'Female business owners are launching successful ventures and creating employment opportunities.',
                'content': '''<h2>Women Leading Business</h2>
<p>Women entrepreneurs in Somalia are <strong>breaking barriers</strong> and establishing successful businesses across various sectors, from technology to retail and services.</p>

<h3>Success Stories</h3>
<ul>
    <li>Tech startups founded by women raising significant funding</li>
    <li>Retail businesses expanding to multiple locations</li>
    <li>Service companies creating jobs for hundreds</li>
    <li>Export businesses reaching international markets</li>
</ul>

<p>These achievements demonstrate the <em>enormous potential</em> of women in business and their contribution to the economy.</p>

<h3>Support Programs</h3>
<p>Various organizations are providing training, mentorship, and financing to support women entrepreneurs.</p>''',
                'status': 'published',
                'priority': 'normal',
                'is_featured': False,
                'is_breaking': False,
            },
            {
                'title': 'Renewable Energy Projects Light Up Rural Areas',
                'excerpt': 'Solar and wind energy installations are bringing electricity to communities for the first time.',
                'content': '''<h2>Powering Communities</h2>
<p>Renewable energy projects are bringing <strong>electricity and light</strong> to rural communities that have never had access to power. Solar and wind installations are transforming lives.</p>

<h3>Project Impact</h3>
<p>The projects include:</p>
<ol>
    <li>Solar panel installations in remote villages</li>
    <li>Wind turbines generating power for communities</li>
    <li>Micro-grid systems connecting households</li>
    <li>Training programs for local technicians</li>
</ol>

<p>These initiatives are providing <em>clean, sustainable energy</em> while creating opportunities for economic development.</p>

<h3>Future Expansion</h3>
<p>Plans are underway to expand these projects to reach even more communities in need of reliable power.</p>''',
                'status': 'published',
                'priority': 'high',
                'is_featured': True,
                'is_breaking': False,
            },
            {
                'title': 'Tourism Sector Sees Record Growth',
                'excerpt': 'Beautiful beaches, historical sites, and cultural experiences are attracting more visitors than ever.',
                'content': '''<h2>Tourism Boom</h2>
<p>Somalia's tourism industry is experiencing <strong>unprecedented growth</strong>, with record numbers of visitors discovering the country's beautiful landscapes, rich history, and vibrant culture.</p>

<h3>Popular Destinations</h3>
<p>Tourists are flocking to:</p>
<ul>
    <li>Pristine beaches along the coastline</li>
    <li>Historical sites and ancient ruins</li>
    <li>Vibrant markets and cultural centers</li>
    <li>Natural parks and wildlife reserves</li>
</ul>

<p>The growing tourism industry is creating <em>thousands of jobs</em> and bringing economic benefits to local communities.</p>

<h3>Investment Opportunities</h3>
<p>Investors are recognizing the potential of Somalia's tourism sector, with new hotels and resorts planned for development.</p>''',
                'status': 'published',
                'priority': 'normal',
                'is_featured': False,
                'is_breaking': False,
            },
        ]

        articles = []
        # Extend the list if we need more than 10 articles
        while len(article_templates) < count:
            article_templates.extend(article_templates)

        selected_templates = article_templates[:count]
        
        # Sample image URLs (you can use placeholder services or existing images)
        image_urls = [
            'https://images.unsplash.com/photo-1504711434969-e92286165efd?w=800',
            'https://images.unsplash.com/photo-1488521787991-ed7bbaae773c?w=800',
            'https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=800',
            'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800',
            'https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=800',
        ]

        for i, template in enumerate(selected_templates):
            # Select random category, tags, and user
            primary_category = random.choice(list(categories))
            secondary_cats = list(categories.exclude(id=primary_category.id))[:2] if categories.count() > 1 else []
            selected_tags = list(tags)[:random.randint(1, min(3, tags.count()))] if tags.exists() else []
            author = random.choice(list(users))
            
            # Generate slug
            slug = StringHelper.slugify(template['title'])
            # Ensure unique slug
            base_slug = slug
            counter = 1
            while Article.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            # Create article
            article = Article.objects.create(
                title=template['title'],
                slug=slug,
                excerpt=template['excerpt'],
                content=template['content'],
                featured_image_url=random.choice(image_urls) if image_urls else None,
                status=template['status'],
                priority=template['priority'],
                author=author,
                primary_category=primary_category,
                is_featured=template.get('is_featured', False),
                is_breaking=template.get('is_breaking', False),
                published_at=timezone.now() - timedelta(days=random.randint(0, 30)),
                view_count=random.randint(10, 1000),
                like_count=random.randint(0, 100),
                share_count=random.randint(0, 50),
                allow_comments=True,
            )
            
            # Add secondary categories and tags
            if secondary_cats:
                article.secondary_categories.set(secondary_cats)
            if selected_tags:
                article.tags.set(selected_tags)
            
            articles.append(article)
            self.stdout.write(
                self.style.SUCCESS(f'Created article: {article.title}')
            )

        return articles

