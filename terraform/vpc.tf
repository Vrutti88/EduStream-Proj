data "aws_vpc" "main" {
  id = "vpc-02767d6c4a2eb7414"
}

data "aws_subnet" "public0" {
  id = "subnet-0eda900a326c09e44"
}

data "aws_subnet" "public1" {
  id = "subnet-0779c6e3ecd7aeaa3"
}

data "aws_subnet" "private0" {
  id = "subnet-07a872c2839c1cdca"
}

data "aws_subnet" "private1" {
  id = "subnet-0524673897791bc10"
}

resource "aws_internet_gateway" "igw" {
  vpc_id = data.aws_vpc.main.id
  tags   = { Name = "${var.project_name}-igw" }
}

resource "aws_route_table" "public" {
  vpc_id = data.aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = { Name = "${var.project_name}-public-rt" }
}

resource "aws_route_table_association" "public0" {
  subnet_id      = data.aws_subnet.public0.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public1" {
  subnet_id      = data.aws_subnet.public1.id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  domain = "vpc"
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id = data.aws_subnet.public0.id

  tags = {
    Name = "${var.project_name}-nat"
  }

  depends_on = [aws_internet_gateway.igw]
}

resource "aws_route_table" "private" {
  vpc_id = data.aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-private-rt"
  }
}

resource "aws_route_table_association" "private0" {
  subnet_id      = data.aws_subnet.private0.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private1" {
  subnet_id      = data.aws_subnet.private1.id
  route_table_id = aws_route_table.private.id
}
