# Apache Kafka Streaming Infrastructure (AWS MSK)

resource "aws_security_group" "msk_sg" {
  count       = var.enable_msk ? 1 : 0
  name        = "${var.project_name}-msk-sg"
  description = "Security group for SentraFlow MSK cluster"

  ingress {
    from_port   = 9092
    to_port     = 9098
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_msk_cluster" "kafka_cluster" {
  count                  = var.enable_msk ? 1 : 0
  cluster_name           = "${var.project_name}-msk"
  kafka_version          = "3.5.1"
  number_of_broker_nodes = 2

  broker_node_group_info {
    instance_type   = "kafka.m5.large"
    client_subnets  = ["subnet-12345678", "subnet-87654321"]
    security_groups = [aws_security_group.msk_sg[0].id]

    storage_info {
      ebs_storage_info {
        volume_size = 100
      }
    }
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
    encryption_at_rest_kms_key_arn = aws_kms_key.lakehouse_key.arn
  }

  tags = {
    Name = "${var.project_name}-msk"
  }
}

