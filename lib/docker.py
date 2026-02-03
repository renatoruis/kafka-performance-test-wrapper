"""Docker command execution"""

import subprocess
from typing import Optional, List


class DockerRunner:
    """Run Kafka CLI commands via Docker"""
    
    def __init__(self, kafka_image: str = 'confluentinc/cp-kafka:7.8.0'):
        self.kafka_image = kafka_image
    
    def run_kafka_cmd(
        self, 
        cmd: List[str], 
        bootstrap_servers: str,
        jar_path: Optional[str] = None,
        payload_file: Optional[str] = None,
        producer_config: Optional[str] = None,
        consumer_config: Optional[str] = None,
        aws_config: Optional[dict] = None
    ) -> subprocess.CompletedProcess:
        """Run Kafka CLI command via Docker
        
        Args:
            cmd: Command and arguments
            bootstrap_servers: Kafka bootstrap servers
            jar_path: Optional MSK IAM JAR path
            payload_file: Optional payload file path
            producer_config: Optional producer config file path
            consumer_config: Optional consumer config file path
            aws_config: Optional AWS credentials dict
        """
        docker_cmd = ['docker', 'run', '--rm']
        
        # Use host network if connecting to localhost
        if 'localhost' in bootstrap_servers or '127.0.0.1' in bootstrap_servers:
            docker_cmd.append('--network=host')
        
        # MSK IAM setup
        if jar_path and aws_config:
            docker_cmd.extend([
                '-v', f'{jar_path}:/opt/msk-iam-auth.jar:ro',
                '-e', 'CLASSPATH=/opt/msk-iam-auth.jar',
                '-e', f'AWS_REGION={aws_config["region"]}',
                '-e', f'AWS_ACCESS_KEY_ID={aws_config["access_key_id"]}',
                '-e', f'AWS_SECRET_ACCESS_KEY={aws_config["secret_access_key"]}',
            ])
            if aws_config.get('session_token'):
                docker_cmd.extend(['-e', f'AWS_SESSION_TOKEN={aws_config["session_token"]}'])
        
        # Mount payload file if provided
        if payload_file:
            docker_payload_path = '/tmp/payload.json'
            docker_cmd.extend(['-v', f'{payload_file}:{docker_payload_path}:ro'])
            # Update command to use Docker path
            cmd = [docker_payload_path if arg == payload_file else arg for arg in cmd]
        
        # Mount producer config if provided
        if producer_config:
            docker_producer_config_path = '/tmp/producer.properties'
            docker_cmd.extend(['-v', f'{producer_config}:{docker_producer_config_path}:ro'])
            # Update command to use Docker path
            cmd = [docker_producer_config_path if arg == producer_config else arg for arg in cmd]
        
        # Mount consumer config if provided
        if consumer_config:
            docker_consumer_config_path = '/tmp/consumer-config.properties'
            docker_cmd.extend(['-v', f'{consumer_config}:{docker_consumer_config_path}:ro'])
            # Update command to use Docker path
            cmd = [docker_consumer_config_path if arg == consumer_config else arg for arg in cmd]
        
        docker_cmd.append(self.kafka_image)
        docker_cmd.extend(cmd)
        
        return subprocess.run(docker_cmd, capture_output=True, text=True)
