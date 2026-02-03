"""AWS MSK IAM authentication setup"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class MSKIAMManager:
    """Manage MSK IAM authentication"""
    
    def __init__(self, config: dict, script_dir: Path):
        self.config = config
        self.script_dir = script_dir
        self.msk_config = config.get('msk_iam', {})
    
    def is_enabled(self) -> bool:
        """Check if MSK IAM is enabled"""
        return self.msk_config.get('enabled', False)
    
    def setup(self, bootstrap_servers: str, producer_config: dict) -> Tuple[str, str, str]:
        """Setup MSK IAM authentication
        
        Returns:
            (jar_path, producer_config_file, consumer_config_file)
        """
        aws_region = self.msk_config.get('region')
        role_arn = self.msk_config.get('role_arn')
        
        if not aws_region:
            raise ValueError("MSK IAM requires aws_region")
        
        # Get AWS credentials
        if role_arn:
            # Assume role if ARN provided
            self._assume_role(role_arn)
        elif not os.environ.get('AWS_ACCESS_KEY_ID'):
            # Try to get credentials from instance role or AWS config
            self._get_session_credentials()
        
        # Verify credentials are available
        if not os.environ.get('AWS_ACCESS_KEY_ID') or not os.environ.get('AWS_SECRET_ACCESS_KEY'):
            raise ValueError("MSK IAM requires AWS credentials (instance role, profile, or environment variables)")
        
        # Download JAR
        jar_path = self._download_jar()
        
        # Create config files
        producer_config_file = self._create_producer_config(bootstrap_servers, producer_config)
        consumer_config_file = self._create_consumer_config(bootstrap_servers)
        
        return str(jar_path), producer_config_file, consumer_config_file
    
    def _get_session_credentials(self):
        """Get AWS credentials from instance role, profile, or environment"""
        if not BOTO3_AVAILABLE:
            print("⚠️  boto3 not available. Install with: pip install boto3")
            print("⚠️  Will try to use existing environment variables")
            return
        
        try:
            # Create session (automatically detects instance role, profile, env vars)
            session = boto3.Session(
                region_name=self.msk_config.get('region'),
                profile_name=self.msk_config.get('profile') or None
            )
            credentials = session.get_credentials()
            
            if credentials:
                print("✅ Using AWS credentials from:", end=" ")
                if os.environ.get('AWS_PROFILE') or self.msk_config.get('profile'):
                    print(f"profile ({self.msk_config.get('profile') or os.environ.get('AWS_PROFILE')})")
                elif os.path.exists('/sys/hypervisor/uuid'):
                    # Likely EC2 instance
                    print("EC2 instance role")
                else:
                    print("AWS configuration")
                
                os.environ['AWS_ACCESS_KEY_ID'] = credentials.access_key
                os.environ['AWS_SECRET_ACCESS_KEY'] = credentials.secret_key
                if credentials.token:
                    os.environ['AWS_SESSION_TOKEN'] = credentials.token
            else:
                print("⚠️  No AWS credentials found")
                
        except Exception as e:
            print(f"⚠️  Failed to get AWS credentials via boto3: {e}")
    
    def _assume_role(self, role_arn: str):
        """Assume AWS role"""
        session_name = self.msk_config.get('session_name', 'kafka-perf')
        
        try:
            cmd = [
                'aws', 'sts', 'assume-role',
                '--role-arn', role_arn,
                '--role-session-name', session_name,
                '--query', 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]',
                '--output', 'text'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            creds = result.stdout.strip().split()
            
            os.environ['AWS_ACCESS_KEY_ID'] = creds[0]
            os.environ['AWS_SECRET_ACCESS_KEY'] = creds[1]
            os.environ['AWS_SESSION_TOKEN'] = creds[2]
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to assume role: {e}")
    
    def _download_jar(self) -> Path:
        """Download MSK IAM auth JAR if needed"""
        jar_version = self.msk_config.get('jar_version', '2.3.5')
        cache_dir = self.script_dir / '.cache'
        cache_dir.mkdir(exist_ok=True)
        jar_path = cache_dir / f'aws-msk-iam-auth-{jar_version}.jar'
        
        if not jar_path.exists():
            jar_url = f'https://repo1.maven.org/maven2/software/amazon/msk/aws-msk-iam-auth/{jar_version}/aws-msk-iam-auth-{jar_version}.jar'
            print(f"Downloading MSK IAM auth jar: {jar_url}")
            subprocess.run(['curl', '-fsSL', jar_url, '-o', str(jar_path)], check=True)
        
        return jar_path
    
    def _create_producer_config(self, bootstrap_servers: str, producer_config: dict) -> str:
        """Create producer configuration file"""
        config_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.properties')
        config_file.write(f"""bootstrap.servers={bootstrap_servers}
acks={producer_config['acks']}
compression.type={producer_config['compression']}
linger.ms={producer_config['linger_ms']}
batch.size={producer_config['batch_size']}
client.id={producer_config.get('client_id', 'perf-cli')}
security.protocol=SASL_SSL
sasl.mechanism=AWS_MSK_IAM
sasl.jaas.config=software.amazon.msk.auth.iam.IAMLoginModule required;
sasl.client.callback.handler.class=software.amazon.msk.auth.iam.IAMClientCallbackHandler
""")
        config_file.close()
        # Set readable permissions for Docker container
        os.chmod(config_file.name, 0o644)
        return config_file.name
    
    def _create_consumer_config(self, bootstrap_servers: str) -> str:
        """Create consumer configuration file"""
        config_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.properties')
        config_file.write(f"""bootstrap.servers={bootstrap_servers}
security.protocol=SASL_SSL
sasl.mechanism=AWS_MSK_IAM
sasl.jaas.config=software.amazon.msk.auth.iam.IAMLoginModule required;
sasl.client.callback.handler.class=software.amazon.msk.auth.iam.IAMClientCallbackHandler
auto.offset.reset=earliest
""")
        config_file.close()
        # Set readable permissions for Docker container
        os.chmod(config_file.name, 0o644)
        return config_file.name
    
    def get_aws_config(self) -> dict:
        """Get AWS configuration for Docker"""
        return {
            'region': self.msk_config['region'],
            'access_key_id': os.environ.get('AWS_ACCESS_KEY_ID'),
            'secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
            'session_token': os.environ.get('AWS_SESSION_TOKEN')
        }
